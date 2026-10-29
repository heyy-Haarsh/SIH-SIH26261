"""Explainable, versioned scrutiny risk prioritization.

The score is a prioritization aid only — never proof of fraud and never an
automatic approve/reject decision. Incomplete processing must not be scored as
compliance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.document import Document
from app.models.enums import (
    ACTIVE_FINDING_VALUES,
    ApplicationStatus,
    DeficiencyStatus,
    FindingSeverity,
    FindingStatus,
    ForensicsIndicatorStatus,
    ForensicsRiskClass,
    ReconciliationItemStatus,
    ReconciliationOutcome,
    ValidationRunStatus,
)
from app.models.forensics import ForensicsIndicator
from app.models.reconciliation import ReconciliationItem
from app.models.review import DeficiencyNotice
from app.models.validation import ValidationRun
from app.services.findings_service import current_findings
from app.core.seed import DEFAULT_DOCS

SCORE_CONFIG_VERSION = "scrutiny-weights-v1"

# Configurable weights (documented in score_breakdown.config)
WEIGHTS: dict[str, int] = {
    "failed_finding": 28,
    "manual_review_finding": 18,
    "warning_finding": 10,
    "info_finding": 2,
    "recon_mismatch": 14,
    "recon_missing_data": 8,
    "recon_possible_duplicate": 10,
    "recon_manual_review": 12,
    "forensics_authenticity_concern": 22,
    "forensics_technical_anomaly": 8,
    "forensics_possible_duplicate": 10,
    "missing_mandatory_document": 24,
    "open_deficiency": 15,
    "partial_processing_penalty": 6,  # incomplete validation — NOT compliance credit
}

MAX_SCORE = 100


@dataclass
class ScoreContribution:
    source: str
    label: str
    weight_key: str
    points: int
    ref_id: str | None = None
    detail: str = ""


@dataclass
class ScoreResult:
    score: int
    config_version: str
    contributions: list[ScoreContribution] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    processing_complete: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "configVersion": self.config_version,
            "weights": dict(WEIGHTS),
            "maxScore": MAX_SCORE,
            "processingComplete": self.processing_complete,
            "disclaimer": (
                "Prioritization aid only — not proof of fraud, compliance, or an automatic rejection."
            ),
            "contributions": [
                {
                    "source": c.source,
                    "label": c.label,
                    "weightKey": c.weight_key,
                    "points": c.points,
                    "refId": c.ref_id,
                    "detail": c.detail,
                }
                for c in self.contributions
            ],
            "notes": self.notes,
        }


def _add(contribs: list[ScoreContribution], *args, **kwargs) -> None:
    contribs.append(ScoreContribution(*args, **kwargs))


def compute_scrutiny_score(db: Session, application: Application) -> ScoreResult:
    contribs: list[ScoreContribution] = []
    notes: list[str] = []
    processing_complete = True

    latest_run = (
        db.query(ValidationRun)
        .filter(ValidationRun.application_id == application.id)
        .order_by(ValidationRun.created_at.desc())
        .first()
    )
    if latest_run is None:
        processing_complete = False
        notes.append(
            "No validation run yet — score reflects incomplete processing, not compliance."
        )
        _add(
            contribs,
            "processing",
            "Validation not run",
            "partial_processing_penalty",
            WEIGHTS["partial_processing_penalty"],
            detail="Missing validation run must not be treated as a clean pass.",
        )
    elif latest_run.status != ValidationRunStatus.COMPLETED:
        processing_complete = False
        notes.append(
            f"Latest validation status is '{latest_run.status.value}' — incomplete; not a clean pass."
        )
        _add(
            contribs,
            "processing",
            "Validation incomplete",
            "partial_processing_penalty",
            WEIGHTS["partial_processing_penalty"],
            ref_id=latest_run.id,
            detail=f"status={latest_run.status.value}",
        )

    # Rule findings (open only)
    findings = list(reversed(current_findings(db, application.id)))
    seen_titles: set[str] = set()
    for f in findings:
        status_val = f.status.value if hasattr(f.status, "value") else str(f.status)
        if status_val not in ACTIVE_FINDING_VALUES:
            continue
        key = f"{f.rule_code}:{f.title}"
        if key in seen_titles:
            continue
        seen_titles.add(key)
        sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
        if sev == FindingSeverity.FAILED.value:
            wk, pts = "failed_finding", WEIGHTS["failed_finding"]
        elif sev == FindingSeverity.MANUAL_REVIEW.value:
            wk, pts = "manual_review_finding", WEIGHTS["manual_review_finding"]
        elif sev == FindingSeverity.WARNING.value:
            wk, pts = "warning_finding", WEIGHTS["warning_finding"]
        else:
            wk, pts = "info_finding", WEIGHTS["info_finding"]
        _add(
            contribs,
            "finding",
            f.title,
            wk,
            pts,
            ref_id=f.id,
            detail=f"severity={sev}; rule={f.rule_code}",
        )

    # Reconciliation open non-MATCH
    recon_items = (
        db.query(ReconciliationItem)
        .filter(
            ReconciliationItem.application_id == application.id,
            ReconciliationItem.status == ReconciliationItemStatus.OPEN,
            ReconciliationItem.outcome != ReconciliationOutcome.MATCH,
        )
        .all()
    )
    for item in recon_items:
        outcome = item.outcome.value
        if outcome == ReconciliationOutcome.MISMATCH.value:
            wk = "recon_mismatch"
        elif outcome == ReconciliationOutcome.MISSING_DATA.value:
            wk = "recon_missing_data"
        elif outcome == ReconciliationOutcome.POSSIBLE_DUPLICATE.value:
            wk = "recon_possible_duplicate"
        else:
            wk = "recon_manual_review"
        _add(
            contribs,
            "reconciliation",
            item.title,
            wk,
            WEIGHTS[wk],
            ref_id=item.id,
            detail=f"outcome={outcome}; field={item.field_name}",
        )

    # Forensics concerns
    for_inds = (
        db.query(ForensicsIndicator)
        .filter(
            ForensicsIndicator.application_id == application.id,
            ForensicsIndicator.status == ForensicsIndicatorStatus.OPEN,
            ForensicsIndicator.risk_class.in_(
                [
                    ForensicsRiskClass.AUTHENTICITY_CONCERN,
                    ForensicsRiskClass.TECHNICAL_ANOMALY,
                    ForensicsRiskClass.POSSIBLE_DUPLICATE,
                ]
            ),
        )
        .all()
    )
    for ind in for_inds:
        rc = ind.risk_class.value
        if rc == ForensicsRiskClass.AUTHENTICITY_CONCERN.value:
            wk = "forensics_authenticity_concern"
        elif rc == ForensicsRiskClass.POSSIBLE_DUPLICATE.value:
            wk = "forensics_possible_duplicate"
        else:
            wk = "forensics_technical_anomaly"
        _add(
            contribs,
            "forensics",
            ind.title,
            wk,
            WEIGHTS[wk],
            ref_id=ind.id,
            detail=f"risk={rc}; code={ind.code.value}",
        )

    # Missing mandatory documents
    from app.services import category_config_service

    reqs = category_config_service.effective_requirements(application)
    uploaded = {d.requirement_code for d in application.documents}
    for req in reqs:
        if not req.get("mandatory"):
            continue
        code = req.get("code")
        if code and code not in uploaded:
            _add(
                contribs,
                "checklist",
                f"Missing mandatory document: {req.get('name', code)}",
                "missing_mandatory_document",
                WEIGHTS["missing_mandatory_document"],
                detail=f"requirement={code}",
            )

    # Open deficiencies
    open_defs = (
        db.query(DeficiencyNotice)
        .filter(
            DeficiencyNotice.application_id == application.id,
            DeficiencyNotice.status == DeficiencyStatus.OPEN,
        )
        .all()
    )
    for d in open_defs:
        _add(
            contribs,
            "deficiency",
            d.title,
            "open_deficiency",
            WEIGHTS["open_deficiency"],
            ref_id=d.id,
            detail="Open clarification / deficiency notice",
        )

    raw = sum(c.points for c in contribs)
    score = min(MAX_SCORE, raw)
    if not contribs:
        notes.append("No open risk contributors — score 0 does not certify compliance.")

    # Terminal recommended/rejected still keep last score for history
    if application.status in (ApplicationStatus.RECOMMENDED, ApplicationStatus.APPROVED):
        notes.append("Application recommended/approved — score remains a historical prioritization aid.")

    return ScoreResult(
        score=score,
        config_version=SCORE_CONFIG_VERSION,
        contributions=contribs,
        notes=notes,
        processing_complete=processing_complete,
    )


def build_scrutiny_summary(db: Session, application: Application, score: ScoreResult) -> dict[str, Any]:
    """Application-level summary combining rules, checklist, recon, forensics."""
    open_findings = [
        f
        for f in current_findings(db, application.id)
        if (f.status.value if hasattr(f.status, "value") else str(f.status)) == "open"
    ]
    recon_open = (
        db.query(ReconciliationItem)
        .filter(
            ReconciliationItem.application_id == application.id,
            ReconciliationItem.status == ReconciliationItemStatus.OPEN,
            ReconciliationItem.outcome != ReconciliationOutcome.MATCH,
        )
        .count()
    )
    for_open = (
        db.query(ForensicsIndicator)
        .filter(
            ForensicsIndicator.application_id == application.id,
            ForensicsIndicator.status == ForensicsIndicatorStatus.OPEN,
            ForensicsIndicator.risk_class.in_(
                [
                    ForensicsRiskClass.AUTHENTICITY_CONCERN,
                    ForensicsRiskClass.TECHNICAL_ANOMALY,
                    ForensicsRiskClass.POSSIBLE_DUPLICATE,
                ]
            ),
        )
        .count()
    )
    open_defs = (
        db.query(DeficiencyNotice)
        .filter(
            DeficiencyNotice.application_id == application.id,
            DeficiencyNotice.status == DeficiencyStatus.OPEN,
        )
        .count()
    )
    docs = db.query(Document).filter(Document.application_id == application.id).count()
    from app.services import category_config_service

    reqs = category_config_service.effective_requirements(application)
    mandatory = [r for r in reqs if r.get("mandatory")]
    uploaded = {d.requirement_code for d in application.documents}
    missing = [r.get("code") for r in mandatory if r.get("code") not in uploaded]

    return {
        "applicationId": application.id,
        "applicationNumber": application.application_number,
        "status": application.status.value if hasattr(application.status, "value") else str(application.status),
        "documentsUploaded": docs,
        "mandatoryMissing": missing,
        "openFindings": len(open_findings),
        "openFindingsBySeverity": {
            "failed": sum(1 for f in open_findings if f.severity == FindingSeverity.FAILED),
            "manual_review": sum(
                1 for f in open_findings if f.severity == FindingSeverity.MANUAL_REVIEW
            ),
            "warning": sum(1 for f in open_findings if f.severity == FindingSeverity.WARNING),
            "info": sum(1 for f in open_findings if f.severity == FindingSeverity.INFO),
        },
        "openReconciliationIssues": recon_open,
        "openForensicsConcerns": for_open,
        "openDeficiencies": open_defs,
        "requiresManualReview": bool(application.requires_manual_review),
        "priorityScore": score.score,
        "score": score.to_dict(),
        "disclaimer": (
            "This summary supports officer scrutiny. It is not an automatic rejection or fraud determination. "
            "Failed or skipped processing steps do not imply compliance."
        ),
    }


def apply_score_to_application(db: Session, application: Application) -> ScoreResult:
    score = compute_scrutiny_score(db, application)
    application.priority_score = score.score
    application.score_config_version = score.config_version
    application.score_breakdown = score.to_dict()
    previous = dict(application.scrutiny_summary or {})
    new_summary = build_scrutiny_summary(db, application, score)
    # A recorded decision is history: re-scoring must never silently erase it.
    for key in ("finalDecision", "finalDecisionReason", "finalDecisionAt", "finalDecisionBy"):
        if key in previous:
            new_summary[key] = previous[key]
    application.scrutiny_summary = new_summary
    application.requires_manual_review = bool(
        score.score >= 25
        or any(c.weight_key in ("failed_finding", "forensics_authenticity_concern") for c in score.contributions)
        or not score.processing_complete
    )
    # Refresh finding / deficiency counts
    application.finding_count = len(current_findings(db, application.id))
    application.deficiency_count = (
        db.query(DeficiencyNotice)
        .filter(
            DeficiencyNotice.application_id == application.id,
            DeficiencyNotice.status == DeficiencyStatus.OPEN,
        )
        .count()
    )
    return score
