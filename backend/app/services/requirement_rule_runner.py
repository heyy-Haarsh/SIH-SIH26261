"""Run the category-specific rules that govern an application.

Which rules apply is decided only by the application's *pinned* configuration snapshot: the
rules attached to the requirement a document answers, at the exact rule versions that were
published in that snapshot. Draft, retired or other-category rules are never consulted, and a
newer configuration is never applied silently.

Every evaluation is stored as a ``RuleCheckResult`` carrying the rule version, document version
and configuration version, and earlier results for the application are marked not-current so a
stale run can never present itself as the latest. "Unable to evaluate" is stored as such; it
produces an informational note for the officer, never a failed compliance finding.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy.orm import Session

from app.document_processing.types import EvidenceDraft, FindingDraft
from app.models.application import Application
from app.models.category_config import RuleCheckResult
from app.models.document import Document, ExtractedField
from app.models.enums import FindingSeverity, ValidationOutcome
from app.models.extraction import ExtractionRun
from app.rules import definition as rd
from app.services import applicant_findings_service as afs
from app.services import category_config_service as ccs

log = logging.getLogger("praman.rule_runner")

_SEVERITY = {
    "failed": (FindingSeverity.FAILED, ValidationOutcome.FAILED),
    "warning": (FindingSeverity.WARNING, ValidationOutcome.WARNING),
    "manual_review": (FindingSeverity.MANUAL_REVIEW, ValidationOutcome.MANUAL_REVIEW),
}


def _fields_for(db: Session, doc: Document) -> dict[str, str]:
    version = doc.latest_version
    if version is None:
        return {}
    out: dict[str, str] = {}
    for ef in db.query(ExtractedField).filter(ExtractedField.document_version_id == version.id):
        if ef.is_conflict and not ef.corrected_value:
            continue
        # Same rule as the platform's other checks: low-confidence values never silently pass.
        if ef.confidence is not None and ef.confidence < 0.55 and not ef.corrected_value:
            continue
        out[ef.field_name] = ef.corrected_value or ef.normalized_value or ef.value
    return out


def _extraction_state(db: Session, doc: Document) -> str:
    version = doc.latest_version
    if version is None:
        return "not_run"
    run = (
        db.query(ExtractionRun)
        .filter(ExtractionRun.document_version_id == version.id)
        .order_by(ExtractionRun.created_at.desc())
        .first()
    )
    state, _ = afs.processing_info(run)
    return state


def evaluate_application(db: Session, app: Application, validation_run_id: str | None) -> list[FindingDraft]:
    """Evaluate every pinned rule for every uploaded document; persist results; return drafts."""
    snap = ccs.pinned_snapshot(app)
    if snap is None or app.config_version is None:
        return []
    cv = app.config_version

    docs = db.query(Document).filter(Document.application_id == app.id).all()
    by_code = {d.requirement_code: d for d in docs}
    fields_by_code = {code: _fields_for(db, d) for code, d in by_code.items()}

    # Everything from earlier runs describes an earlier state; keep it as history, not as current.
    db.query(RuleCheckResult).filter(
        RuleCheckResult.application_id == app.id, RuleCheckResult.is_current.is_(True)
    ).update({RuleCheckResult.is_current: False}, synchronize_session=False)

    drafts: list[FindingDraft] = []
    for req in snap.get("requirements", []):
        rules = req.get("rules") or []
        if not rules:
            continue
        doc = by_code.get(req["code"])
        if doc is None or doc.latest_version is None:
            continue  # a missing mandatory document is reported by the checklist, not by its rules
        version = doc.latest_version
        state = _extraction_state(db, doc)
        data = rd.RuleInput(
            fields=fields_by_code.get(req["code"], {}),
            extension=version.extension or "",
            size_bytes=version.size_bytes or 0,
            extraction_state=state,
            other_documents={c: f for c, f in fields_by_code.items() if c != req["code"]},
            today=date.today(),
        )
        for rule in rules:
            definition = rule["definition"]
            try:
                result = rd.evaluate(definition, data)
            except Exception as exc:  # noqa: BLE001 — one bad rule must not stop the others
                log.exception("Rule %s could not be evaluated", rule.get("code"))
                result = rd.CheckResult(rd.UNABLE, f"The rule could not be run ({exc.__class__.__name__}).", {})
            severity_key = rd.severity_of(definition)
            db.add(
                RuleCheckResult(
                    application_id=app.id,
                    document_id=doc.id,
                    document_version=version.version,
                    requirement_id=req.get("id") or "",
                    requirement_code=req["code"],
                    rule_id=rule["rule_id"],
                    rule_version_id=rule["rule_version_id"],
                    rule_version=rule["rule_version"],
                    rule_code=rule["code"],
                    rule_title=rule["title"],
                    config_version_id=cv.id,
                    config_version=cv.version,
                    validation_run_id=validation_run_id,
                    state=result.state,
                    severity=severity_key,
                    message=result.message,
                    inputs=result.inputs,
                    is_current=True,
                )
            )
            evidence = [
                EvidenceDraft(
                    description=f"{rule['title']} (rule v{rule['rule_version']}, configuration v{cv.version}): {result.message}",
                    document_id=doc.id,
                    document_name=version.file_name,
                )
            ]
            if result.state in (rd.FAILED, rd.MANUAL_REVIEW):
                sev, outcome = _SEVERITY[severity_key]
                if result.state == rd.MANUAL_REVIEW:
                    sev, outcome = FindingSeverity.MANUAL_REVIEW, ValidationOutcome.MANUAL_REVIEW
                drafts.append(
                    FindingDraft(
                        title=rule["title"],
                        description=result.message,
                        severity=sev,
                        outcome=outcome,
                        rule_code=rule["code"],
                        rule_name=rule["title"],
                        rule_version=f"v{rule['rule_version']}",
                        handbook_ref=rule.get("source_reference") or "",
                        document_id=doc.id,
                        evidence=evidence,
                    )
                )
            elif result.state in (rd.UNABLE, rd.SOURCE_UNAVAILABLE):
                # A limitation of the system, recorded for the officer, not a compliance failure.
                drafts.append(
                    FindingDraft(
                        title=f"Could not evaluate: {rule['title']}",
                        description=result.message,
                        severity=FindingSeverity.INFO,
                        outcome=ValidationOutcome.VERIFICATION_UNAVAILABLE,
                        rule_code=rule["code"],
                        rule_name=rule["title"],
                        rule_version=f"v{rule['rule_version']}",
                        handbook_ref=rule.get("source_reference") or "",
                        document_id=doc.id,
                        evidence=evidence,
                    )
                )
    db.flush()
    return drafts
