"""Persist and resolve cross-document reconciliation runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.core.errors import ForbiddenError, NotFoundError, UnprocessableError
from app.document_processing.reconciliation import (
    ENGINE_VERSION,
    BasicReconciliationModule,
    DocMeta,
)
from app.document_processing.types import DiscrepancyDraft, FieldRecord
from app.models.application import Application
from app.models.base import utcnow
from app.models.document import Document, ExtractedField
from app.models.enums import (
    ReconciliationItemStatus,
    ReconciliationOutcome,
    ReconciliationRunStatus,
    UserRole,
)
from app.models.extraction import ExtractionRun
from app.models.reconciliation import ReconciliationItem, ReconciliationRun, ReconciliationValue
from app.models.user import User
from app.services.audit_service import record_audit

RESOLVE_STATUSES = {
    ReconciliationItemStatus.RESOLVED,
    ReconciliationItemStatus.WAIVED,
    ReconciliationItemStatus.ACCEPTED,
}


def _fields_for_version(db: Session, document_version_id: str) -> list[ExtractedField]:
    return (
        db.query(ExtractedField)
        .filter(ExtractedField.document_version_id == document_version_id)
        .all()
    )


def collect_field_records(db: Session, application_id: str) -> tuple[list[FieldRecord], list[DocMeta]]:
    docs = db.query(Document).filter(Document.application_id == application_id).all()
    field_records: list[FieldRecord] = []
    doc_metas: list[DocMeta] = []

    for d in docs:
        version = d.latest_version
        if not version:
            continue
        doc_metas.append(
            DocMeta(
                document_id=d.id,
                document_name=version.file_name,
                sha256=version.sha256 or "",
                requirement_code=d.requirement_code,
            )
        )
        # Prefer fields from latest extraction run when present
        latest_ext = (
            db.query(ExtractionRun)
            .filter(ExtractionRun.document_version_id == version.id)
            .order_by(ExtractionRun.created_at.desc())
            .first()
        )
        db_fields = _fields_for_version(db, version.id)
        if latest_ext:
            run_fields = [f for f in db_fields if f.extraction_run_id == latest_ext.id]
            if run_fields:
                db_fields = run_fields

        for ef in db_fields:
            if ef.is_conflict and not ef.corrected_value:
                continue
            if ef.confidence is not None and ef.confidence < 0.55 and not ef.corrected_value:
                continue
            value = ef.corrected_value or ef.normalized_value or ef.value
            if not (value or "").strip():
                continue
            field_records.append(
                FieldRecord(
                    field_name=ef.field_name,
                    value=value,
                    document_id=d.id,
                    document_name=version.file_name,
                    page_reference=ef.page_reference,
                    page_number=ef.page_number,
                    extracted_field_id=ef.id,
                    evidence_snippet=(
                        f'{version.file_name}'
                        + (f' p.{ef.page_number}' if ef.page_number else "")
                        + f': "{value}"'
                    ),
                )
            )
    return field_records, doc_metas


def _persist_item(
    db: Session,
    *,
    run: ReconciliationRun,
    application_id: str,
    draft: DiscrepancyDraft,
) -> ReconciliationItem:
    item = ReconciliationItem(
        run_id=run.id,
        application_id=application_id,
        field_name=draft.field_name,
        outcome=draft.outcome,
        original_outcome=draft.outcome,
        match_kind=draft.match_kind,
        severity=draft.severity,
        status=ReconciliationItemStatus.OPEN,
        title=draft.title or draft.field_name,
        description=draft.description or "",
        fingerprint=draft.fingerprint or "",
    )
    db.add(item)
    db.flush()
    for v in draft.values:
        db.add(
            ReconciliationValue(
                item_id=item.id,
                document_id=v.document_id,
                document_name=v.document_name,
                extracted_field_id=v.extracted_field_id,
                value=v.value,
                normalized_value=v.normalized_value,
                page_number=v.page_number,
                page_reference=v.page,
                evidence_snippet=v.evidence_snippet,
            )
        )
    return item


def run_reconciliation(
    db: Session,
    application: Application,
    *,
    triggered_by: str | None,
    actor_name: str,
    trigger: str = "validation",
    validation_run_id: str | None = None,
    commit: bool = True,
) -> ReconciliationRun:
    """Compare extracted fields, persist a run, dedupe open findings, clear stale ones."""
    field_records, doc_metas = collect_field_records(db, application.id)
    module = BasicReconciliationModule()
    compared = module.compare(field_records, documents=doc_metas)

    now = datetime.now(timezone.utc)
    run = ReconciliationRun(
        application_id=application.id,
        validation_run_id=validation_run_id,
        status=ReconciliationRunStatus.RUNNING,
        trigger=trigger,
        triggered_by_id=triggered_by,
        engine_version=ENGINE_VERSION,
        input_fingerprint=compared.input_fingerprint,
        summary={},
        started_at=now,
    )
    db.add(run)
    db.flush()

    open_items = (
        db.query(ReconciliationItem)
        .filter(
            ReconciliationItem.application_id == application.id,
            ReconciliationItem.status == ReconciliationItemStatus.OPEN,
        )
        .all()
    )
    open_by_fp = {i.fingerprint: i for i in open_items}

    # Resolved fingerprints should not reopen automatically on identical rerun
    resolved_fps = {
        i.fingerprint
        for i in db.query(ReconciliationItem)
        .filter(
            ReconciliationItem.application_id == application.id,
            ReconciliationItem.status.in_(list(RESOLVE_STATUSES)),
        )
        .all()
    }

    created = 0
    reused = 0
    active_fps: set[str] = set()

    for draft in compared.drafts:
        fp = draft.fingerprint or ""
        active_fps.add(fp)

        if fp in open_by_fp:
            # Same open finding — keep it; refresh run association for traceability
            existing = open_by_fp[fp]
            existing.run_id = run.id
            existing.updated_at = utcnow()
            reused += 1
            continue

        if fp in resolved_fps and draft.outcome != ReconciliationOutcome.MATCH:
            # Officer already resolved this exact conflict; do not recreate
            reused += 1
            continue

        # MATCH items: always record on the run for the "matched fields" view,
        # but only keep one open MATCH per fingerprint.
        _persist_item(db, run=run, application_id=application.id, draft=draft)
        created += 1

    cleared = 0
    for item in open_items:
        if item.fingerprint in active_fps:
            continue
        # Only clear non-MATCH stale conflicts (MATCH rows from prior runs can expire quietly)
        if item.outcome == ReconciliationOutcome.MATCH:
            item.status = ReconciliationItemStatus.CLEARED
            item.resolution_reason = "Superseded by newer reconciliation run"
            item.resolved_at = utcnow()
            cleared += 1
            continue
        item.status = ReconciliationItemStatus.CLEARED
        item.resolution_reason = (
            "Cleared on reconciliation rerun — values now consistent or field no longer compared"
        )
        item.resolved_at = utcnow()
        cleared += 1
        record_audit(
            db,
            action="reconciliation.item_cleared",
            actor=actor_name,
            actor_id=triggered_by,
            detail=f"{item.field_name} ({item.outcome.value}) fingerprint={item.fingerprint[:12]}",
            application_id=application.id,
        )

    counts = {
        "MATCH": 0,
        "MISMATCH": 0,
        "MISSING_DATA": 0,
        "POSSIBLE_DUPLICATE": 0,
        "MANUAL_REVIEW": 0,
    }
    for d in compared.drafts:
        counts[d.outcome.value] = counts.get(d.outcome.value, 0) + 1

    open_unresolved = (
        db.query(ReconciliationItem)
        .filter(
            ReconciliationItem.application_id == application.id,
            ReconciliationItem.status == ReconciliationItemStatus.OPEN,
            ReconciliationItem.outcome != ReconciliationOutcome.MATCH,
        )
        .count()
    )

    run.status = ReconciliationRunStatus.COMPLETED
    run.completed_at = datetime.now(timezone.utc)
    run.summary = {
        "counts": counts,
        "created": created,
        "reused": reused,
        "cleared": cleared,
        "openUnresolved": open_unresolved,
        "documentsCompared": len(doc_metas),
        "fieldsCompared": len({r.field_name for r in field_records}),
        "note": "Outcomes are not fraud determinations",
    }

    record_audit(
        db,
        action="reconciliation.run_completed",
        actor=actor_name,
        actor_id=triggered_by,
        detail=json.dumps(
            {
                "runId": run.id,
                "created": created,
                "reused": reused,
                "cleared": cleared,
                "counts": counts,
            }
        ),
        application_id=application.id,
    )

    if commit:
        db.commit()
        db.refresh(run)
    return run


def get_latest_run(db: Session, application_id: str) -> ReconciliationRun | None:
    return (
        db.query(ReconciliationRun)
        .options(joinedload(ReconciliationRun.items).joinedload(ReconciliationItem.values))
        .filter(ReconciliationRun.application_id == application_id)
        .order_by(ReconciliationRun.created_at.desc())
        .first()
    )


def list_open_items_for_application(db: Session, application_id: str) -> list[ReconciliationItem]:
    """Active open items (including MATCH) for application detail serialization."""
    return (
        db.query(ReconciliationItem)
        .options(joinedload(ReconciliationItem.values))
        .filter(
            ReconciliationItem.application_id == application_id,
            ReconciliationItem.status == ReconciliationItemStatus.OPEN,
        )
        .order_by(ReconciliationItem.created_at.desc())
        .all()
    )


def resolve_item(
    db: Session,
    user: User,
    item_id: str,
    *,
    status: ReconciliationItemStatus,
    reason: str,
) -> ReconciliationItem:
    if user.role not in (UserRole.OFFICER, UserRole.ADMIN):
        raise ForbiddenError("Only scrutiny officers or admins may resolve reconciliation items.")
    if status not in RESOLVE_STATUSES:
        raise UnprocessableError(
            f"Invalid resolution status. Allowed: {[s.value for s in RESOLVE_STATUSES]}"
        )
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise UnprocessableError("A resolution reason of at least 5 characters is required.")

    item = (
        db.query(ReconciliationItem)
        .options(joinedload(ReconciliationItem.values))
        .filter(ReconciliationItem.id == item_id)
        .first()
    )
    if not item:
        raise NotFoundError("Reconciliation item not found")

    # Preserve original outcome; only status/reason change
    item.status = status
    item.resolution_reason = reason
    item.resolved_by_id = user.id
    item.resolved_at = utcnow()

    record_audit(
        db,
        action="reconciliation.item_resolved",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=(
            f"item={item.id} field={item.field_name} original_outcome={item.original_outcome.value} "
            f"status={status.value} reason={reason}"
        ),
        application_id=item.application_id,
    )
    db.commit()
    db.refresh(item)
    return item


def drafts_for_validation(db: Session, application_id: str) -> list[DiscrepancyDraft]:
    """Non-MATCH open items as DiscrepancyDrafts for the rule engine."""
    items = (
        db.query(ReconciliationItem)
        .options(joinedload(ReconciliationItem.values))
        .filter(
            ReconciliationItem.application_id == application_id,
            ReconciliationItem.status == ReconciliationItemStatus.OPEN,
            ReconciliationItem.outcome != ReconciliationOutcome.MATCH,
        )
        .all()
    )
    from app.document_processing.types import DiscrepancyValue

    drafts: list[DiscrepancyDraft] = []
    for item in items:
        drafts.append(
            DiscrepancyDraft(
                field_name=item.field_name,
                values=[
                    DiscrepancyValue(
                        document_id=v.document_id,
                        document_name=v.document_name,
                        value=v.value,
                        page=v.page_reference,
                        page_number=v.page_number,
                        extracted_field_id=v.extracted_field_id,
                        normalized_value=v.normalized_value,
                        evidence_snippet=v.evidence_snippet,
                    )
                    for v in item.values
                ],
                outcome=item.outcome,
                severity=item.severity,
                title=item.title,
                description=item.description,
                match_kind=item.match_kind,
                fingerprint=item.fingerprint,
            )
        )
    return drafts
