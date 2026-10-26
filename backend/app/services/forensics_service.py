"""Persist and resolve authenticity / forensics analysis runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session, joinedload

from app.core.errors import ForbiddenError, NotFoundError, UnprocessableError
from app.document_processing.forensics import (
    ENGINE_VERSION,
    DocForensicsInput,
    ForensicsIndicatorDraft,
    LocalForensicsModule,
)
from app.integrations.base import VerificationClaim
from app.integrations.registry import get_verification_adapter
from app.models.application import Application
from app.models.base import utcnow
from app.models.document import Document
from app.models.enums import (
    FindingSeverity,
    ForensicsIndicatorCode,
    ForensicsIndicatorStatus,
    ForensicsRiskClass,
    ForensicsRunStatus,
    UserRole,
    VerificationSource,
    VerificationStatus,
)
from app.models.forensics import ForensicsEvidence, ForensicsIndicator, ForensicsRun
from app.models.user import User
from app.document_processing.types import EvidenceDraft, FindingDraft
from app.models.enums import ValidationOutcome
from app.services.audit_service import record_audit

RESOLVE_STATUSES = {
    ForensicsIndicatorStatus.RESOLVED,
    ForensicsIndicatorStatus.WAIVED,
    ForensicsIndicatorStatus.ACCEPTED,
}

# Indicators that become validation findings (skip pure informational noise)
_FINDING_RISKS = {
    ForensicsRiskClass.TECHNICAL_ANOMALY,
    ForensicsRiskClass.AUTHENTICITY_CONCERN,
    ForensicsRiskClass.POSSIBLE_DUPLICATE,
}


def _load_docs(db: Session, application_id: str) -> list[DocForensicsInput]:
    docs = db.query(Document).filter(Document.application_id == application_id).all()
    out: list[DocForensicsInput] = []
    for d in docs:
        version = d.latest_version
        if not version:
            continue
        content = None
        path = version.storage_path or ""
        if path and Path(path).is_file():
            try:
                content = Path(path).read_bytes()
            except OSError:
                content = None
        out.append(
            DocForensicsInput(
                document_id=d.id,
                document_name=version.file_name,
                extension=version.extension or "",
                mime_type=version.mime_type or "",
                sha256=version.sha256 or "",
                storage_path=path,
                content=content,
            )
        )
    return out


def _persist_indicator(
    db: Session, *, run: ForensicsRun, application_id: str, draft: ForensicsIndicatorDraft
) -> ForensicsIndicator:
    item = ForensicsIndicator(
        run_id=run.id,
        application_id=application_id,
        document_id=draft.document_id,
        code=draft.code,
        risk_class=draft.risk_class,
        original_risk_class=draft.risk_class,
        severity=draft.severity,
        status=ForensicsIndicatorStatus.OPEN,
        verification_status=draft.verification_status,
        title=draft.title,
        description=draft.description,
        affected_pages=list(draft.affected_pages or []),
        fingerprint=draft.fingerprint,
        indicator_metadata=dict(draft.metadata or {}),
    )
    db.add(item)
    db.flush()
    for ev in draft.evidence:
        db.add(
            ForensicsEvidence(
                indicator_id=item.id,
                description=ev.description,
                document_id=ev.document_id or draft.document_id,
                document_name=ev.document_name or draft.document_name,
                page_number=ev.page_number,
                page_reference=ev.page_reference,
                detail=ev.detail,
            )
        )
    return item


def _external_claim_indicators(application_id: str) -> list[ForensicsIndicatorDraft]:
    """Label external authenticity claims as simulated or unavailable — never invent live proof."""
    from app.document_processing.forensics import ForensicsEvidenceDraft, _fp

    adapter = get_verification_adapter()
    outcome = adapter.verify(
        VerificationClaim(
            claim_type="document_authenticity",
            claim="Issuing-authority document authenticity",
            subject={"application_id": application_id},
        )
    )
    if outcome.source == VerificationSource.SIMULATED_DEV or outcome.status == VerificationStatus.SIMULATED_RESULT:
        code = ForensicsIndicatorCode.EXTERNAL_CLAIM_SIMULATED
        risk = ForensicsRiskClass.CHECK_LIMITATION
        title = "External authenticity check is simulated"
        description = (
            f"Adapter '{outcome.adapter}' returned a simulated result. "
            f"{outcome.detail} Not an authorised live verification — not a fraud determination."
        )
        verification = VerificationStatus.SIMULATED_RESULT
    else:
        code = ForensicsIndicatorCode.EXTERNAL_CLAIM_UNAVAILABLE
        risk = ForensicsRiskClass.CHECK_LIMITATION
        title = "External authenticity source unavailable"
        description = (
            f"Adapter '{outcome.adapter}': {outcome.detail} "
            "Missing live verification does not imply the document is fraudulent."
        )
        verification = outcome.status

    return [
        ForensicsIndicatorDraft(
            code=code,
            risk_class=risk,
            severity=FindingSeverity.INFO,
            title=title,
            description=description,
            verification_status=verification,
            evidence=[
                ForensicsEvidenceDraft(
                    description=f"adapter={outcome.adapter}; source={outcome.source.value}; status={outcome.status.value}",
                    detail=outcome.detail,
                )
            ],
            fingerprint=_fp(code.value, application_id, outcome.adapter),
            metadata={"adapter": outcome.adapter, "source": outcome.source.value},
        )
    ]


def run_forensics(
    db: Session,
    application: Application,
    *,
    triggered_by: str | None,
    actor_name: str,
    trigger: str = "validation",
    validation_run_id: str | None = None,
    commit: bool = True,
) -> ForensicsRun:
    docs = _load_docs(db, application.id)
    module = LocalForensicsModule()
    compared = module.compare_documents(docs)
    compared.indicators.extend(_external_claim_indicators(application.id))

    now = datetime.now(timezone.utc)
    run = ForensicsRun(
        application_id=application.id,
        validation_run_id=validation_run_id,
        status=ForensicsRunStatus.RUNNING,
        trigger=trigger,
        triggered_by_id=triggered_by,
        engine_version=ENGINE_VERSION,
        input_fingerprint=compared.input_fingerprint,
        summary={},
        limitations=list(compared.limitations),
        started_at=now,
    )
    db.add(run)
    db.flush()

    open_items = (
        db.query(ForensicsIndicator)
        .filter(
            ForensicsIndicator.application_id == application.id,
            ForensicsIndicator.status == ForensicsIndicatorStatus.OPEN,
        )
        .all()
    )
    open_by_fp = {i.fingerprint: i for i in open_items}
    resolved_fps = {
        i.fingerprint
        for i in db.query(ForensicsIndicator)
        .filter(
            ForensicsIndicator.application_id == application.id,
            ForensicsIndicator.status.in_(list(RESOLVE_STATUSES)),
        )
        .all()
    }

    created = reused = cleared = 0
    active_fps: set[str] = set()

    for draft in compared.indicators:
        fp = draft.fingerprint
        active_fps.add(fp)
        if fp in open_by_fp:
            existing = open_by_fp[fp]
            existing.run_id = run.id
            existing.updated_at = utcnow()
            reused += 1
            continue
        if fp in resolved_fps and draft.risk_class in _FINDING_RISKS:
            reused += 1
            continue
        _persist_indicator(db, run=run, application_id=application.id, draft=draft)
        created += 1

    for item in open_items:
        if item.fingerprint in active_fps:
            continue
        item.status = ForensicsIndicatorStatus.CLEARED
        item.resolution_reason = "Cleared on forensics rerun — indicator no longer present"
        item.resolved_at = utcnow()
        cleared += 1
        record_audit(
            db,
            action="forensics.indicator_cleared",
            actor=actor_name,
            actor_id=triggered_by,
            detail=f"{item.code.value} fingerprint={item.fingerprint[:12]}",
            application_id=application.id,
        )

    counts: dict[str, int] = {}
    for d in compared.indicators:
        counts[d.risk_class.value] = counts.get(d.risk_class.value, 0) + 1

    open_concerns = (
        db.query(ForensicsIndicator)
        .filter(
            ForensicsIndicator.application_id == application.id,
            ForensicsIndicator.status == ForensicsIndicatorStatus.OPEN,
            ForensicsIndicator.risk_class.in_(list(_FINDING_RISKS)),
        )
        .count()
    )

    run.status = ForensicsRunStatus.COMPLETED
    run.completed_at = datetime.now(timezone.utc)
    run.summary = {
        "countsByRiskClass": counts,
        "created": created,
        "reused": reused,
        "cleared": cleared,
        "openConcerns": open_concerns,
        "documentsAnalyzed": len(docs),
        "note": "Indicators are not fraud determinations",
    }

    record_audit(
        db,
        action="forensics.run_completed",
        actor=actor_name,
        actor_id=triggered_by,
        detail=json.dumps(
            {"runId": run.id, "created": created, "reused": reused, "cleared": cleared, "counts": counts}
        ),
        application_id=application.id,
    )

    if commit:
        db.commit()
        db.refresh(run)
    return run


def get_latest_run(db: Session, application_id: str) -> ForensicsRun | None:
    return (
        db.query(ForensicsRun)
        .options(joinedload(ForensicsRun.indicators).joinedload(ForensicsIndicator.evidence))
        .filter(ForensicsRun.application_id == application_id)
        .order_by(ForensicsRun.created_at.desc())
        .first()
    )


def list_open_indicators(db: Session, application_id: str) -> list[ForensicsIndicator]:
    return (
        db.query(ForensicsIndicator)
        .options(joinedload(ForensicsIndicator.evidence))
        .filter(
            ForensicsIndicator.application_id == application_id,
            ForensicsIndicator.status == ForensicsIndicatorStatus.OPEN,
        )
        .order_by(ForensicsIndicator.created_at.desc())
        .all()
    )


def resolve_indicator(
    db: Session,
    user: User,
    indicator_id: str,
    *,
    status: ForensicsIndicatorStatus,
    reason: str,
) -> ForensicsIndicator:
    if user.role not in (UserRole.OFFICER, UserRole.ADMIN):
        raise ForbiddenError("Only scrutiny officers or admins may resolve forensics indicators.")
    if status not in RESOLVE_STATUSES:
        raise UnprocessableError(
            f"Invalid resolution status. Allowed: {[s.value for s in RESOLVE_STATUSES]}"
        )
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise UnprocessableError("A resolution reason of at least 5 characters is required.")

    item = (
        db.query(ForensicsIndicator)
        .options(joinedload(ForensicsIndicator.evidence))
        .filter(ForensicsIndicator.id == indicator_id)
        .first()
    )
    if not item:
        raise NotFoundError("Forensics indicator not found")

    item.status = status
    item.resolution_reason = reason
    item.resolved_by_id = user.id
    item.resolved_at = utcnow()

    record_audit(
        db,
        action="forensics.indicator_resolved",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=(
            f"indicator={item.id} code={item.code.value} original_risk={item.original_risk_class.value} "
            f"status={status.value} reason={reason}"
        ),
        application_id=item.application_id,
    )
    db.commit()
    db.refresh(item)
    return item


def drafts_for_validation(db: Session, application_id: str) -> list[FindingDraft]:
    """Open technical/authenticity/duplicate indicators as FindingDrafts for aggregation."""
    items = (
        db.query(ForensicsIndicator)
        .options(joinedload(ForensicsIndicator.evidence))
        .filter(
            ForensicsIndicator.application_id == application_id,
            ForensicsIndicator.status == ForensicsIndicatorStatus.OPEN,
            ForensicsIndicator.risk_class.in_(list(_FINDING_RISKS)),
        )
        .all()
    )
    drafts: list[FindingDraft] = []
    for item in items:
        outcome = ValidationOutcome.MANUAL_REVIEW
        if item.severity == FindingSeverity.WARNING:
            outcome = ValidationOutcome.WARNING
        elif item.severity == FindingSeverity.INFO:
            outcome = ValidationOutcome.PASS
        drafts.append(
            FindingDraft(
                title=item.title,
                description=(
                    f"{item.description} Risk class: {item.risk_class.value}. "
                    "Not a fraud determination."
                ),
                severity=item.severity,
                outcome=outcome,
                rule_code="SYN-RULE-FOR-001",
                rule_name="[SYNTHETIC] Document authenticity / tamper-risk indicators",
                rule_version="v0.1-demo",
                handbook_ref="Demo handbook §forensics (placeholder)",
                document_id=item.document_id,
                evidence=[
                    EvidenceDraft(
                        description=e.description,
                        document_id=e.document_id,
                        document_name=e.document_name,
                        page_reference=e.page_reference,
                    )
                    for e in item.evidence
                ],
            )
        )
    return drafts
