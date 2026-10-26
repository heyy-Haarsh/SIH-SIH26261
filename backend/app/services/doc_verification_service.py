"""Application service for Phase 7 document verification pipeline."""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.core.errors import ForbiddenError, NotFoundError, UnprocessableError
from app.core.security import ensure_application_access
from app.models.application import Application
from app.models.base import utcnow
from app.models.doc_verification import DocumentVerificationCheck, DocumentVerificationRun
from app.models.document import Document
from app.models.enums import DocumentReviewStatus, UserRole
from app.models.user import User
from app.services.audit_service import record_audit
from app.verification_engine.loader import list_configs
from app.verification_engine.pipeline import run_for_application, run_for_document


def _get_app(db: Session, application_id: str) -> Application:
    app = db.get(Application, application_id)
    if not app:
        raise NotFoundError("Application not found")
    return app


def list_engine_configs() -> list[dict]:
    return [
        {
            "code": c.get("code"),
            "requirementCode": c.get("requirement_code"),
            "name": c.get("name"),
            "version": c.get("version"),
            "isSyntheticRules": bool(c.get("is_synthetic_rules", True)),
            "handbookNote": c.get("handbook_note"),
            "adapters": [a.get("id") for a in (c.get("layer2") or {}).get("adapters") or []],
        }
        for c in list_configs()
    ]


def run_application_pipeline(
    db: Session,
    user: User,
    application_id: str,
) -> list[DocumentVerificationRun]:
    if user.role not in (UserRole.OFFICER, UserRole.ADMIN, UserRole.APPLICANT):
        raise ForbiddenError("Insufficient permissions")
    app = _get_app(db, application_id)
    ensure_application_access(user, app)
    return run_for_application(db, app, triggered_by=user, commit=True)


def run_document_pipeline(
    db: Session, user: User, document_id: str
) -> DocumentVerificationRun:
    if user.role not in (UserRole.OFFICER, UserRole.ADMIN, UserRole.APPLICANT):
        raise ForbiddenError("Insufficient permissions")
    doc = db.get(Document, document_id)
    if not doc:
        raise NotFoundError("Document not found")
    app = _get_app(db, doc.application_id)
    ensure_application_access(user, app)
    run = run_for_document(db, doc, triggered_by=user, commit=True)
    if not run:
        raise UnprocessableError(
            f"No Phase 7 verification config for requirement '{doc.requirement_code}'."
        )
    return run


def list_runs_for_application(db: Session, user: User, application_id: str) -> list[DocumentVerificationRun]:
    app = _get_app(db, application_id)
    ensure_application_access(user, app)
    return (
        db.query(DocumentVerificationRun)
        .options(joinedload(DocumentVerificationRun.checks))
        .filter(DocumentVerificationRun.application_id == application_id)
        .order_by(DocumentVerificationRun.created_at.desc())
        .all()
    )


def get_run(db: Session, user: User, run_id: str) -> DocumentVerificationRun:
    run = (
        db.query(DocumentVerificationRun)
        .options(joinedload(DocumentVerificationRun.checks))
        .filter(DocumentVerificationRun.id == run_id)
        .first()
    )
    if not run:
        raise NotFoundError("Verification run not found")
    app = _get_app(db, run.application_id)
    ensure_application_access(user, app)
    return run


def resolve_check(
    db: Session,
    user: User,
    check_id: str,
    *,
    status: str,
    reason: str,
) -> DocumentVerificationCheck:
    if user.role not in (UserRole.OFFICER, UserRole.ADMIN):
        raise ForbiddenError("Only officers may resolve verification checks.")
    reason = (reason or "").strip()
    if len(reason) < 5:
        raise UnprocessableError("A reason of at least 5 characters is required.")
    if status not in ("resolved", "waived", "accepted"):
        raise UnprocessableError("status must be resolved, waived, or accepted.")

    check = db.get(DocumentVerificationCheck, check_id)
    if not check:
        raise NotFoundError("Verification check not found")
    app = _get_app(db, check.application_id)
    ensure_application_access(user, app)

    check.status = status
    check.resolution_reason = reason
    check.resolved_by_id = user.id
    check.resolved_at = utcnow()

    # Update document review status when all review-layer opens are closed
    open_review = (
        db.query(DocumentVerificationCheck)
        .filter(
            DocumentVerificationCheck.document_id == check.document_id,
            DocumentVerificationCheck.status == "open",
            DocumentVerificationCheck.severity.in_(["failed", "manual_review", "warning"]),
        )
        .count()
    )
    doc = db.get(Document, check.document_id)
    if doc and open_review == 0:
        doc.review_status = (
            DocumentReviewStatus.WAIVED
            if status == "waived"
            else DocumentReviewStatus.ACCEPTED
            if status == "accepted"
            else DocumentReviewStatus.RESOLVED
        )
        run = db.get(DocumentVerificationRun, check.run_id)
        if run:
            run.review_status = doc.review_status

    record_audit(
        db,
        action="doc_verification.check_resolved",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=f"check={check.id}; status={status}; reason={reason[:200]}",
        application_id=check.application_id,
        entity_type="document_verification_check",
        entity_id=check.id,
    )
    db.commit()
    db.refresh(check)
    return check


def check_to_dict(c: DocumentVerificationCheck) -> dict:
    return {
        "id": c.id,
        "runId": c.run_id,
        "applicationId": c.application_id,
        "documentId": c.document_id,
        "layer": c.layer.value if hasattr(c.layer, "value") else c.layer,
        "checkCode": c.check_code,
        "title": c.title,
        "detail": c.detail,
        "outcome": c.outcome,
        "severity": c.severity,
        "source": c.source.value if hasattr(c.source, "value") else c.source,
        "adapter": c.adapter,
        "isSyntheticRule": c.is_synthetic_rule,
        "evidence": c.evidence or {},
        "limitations": c.limitations or [],
        "status": c.status,
        "resolutionReason": c.resolution_reason,
        "resolvedAt": c.resolved_at,
        "createdAt": c.created_at,
    }


def run_to_dict(r: DocumentVerificationRun) -> dict:
    return {
        "id": r.id,
        "applicationId": r.application_id,
        "documentId": r.document_id,
        "documentVersionId": r.document_version_id,
        "validationRunId": r.validation_run_id,
        "configCode": r.config_code,
        "configVersion": r.config_version,
        "status": r.status.value if hasattr(r.status, "value") else r.status,
        "ruleValidationStatus": r.rule_validation_status.value
        if hasattr(r.rule_validation_status, "value")
        else r.rule_validation_status,
        "externalVerificationStatus": r.external_verification_status.value
        if hasattr(r.external_verification_status, "value")
        else r.external_verification_status,
        "reviewStatus": r.review_status.value if hasattr(r.review_status, "value") else r.review_status,
        "summary": r.summary or {},
        "limitations": r.limitations or [],
        "scrutinyReport": r.scrutiny_report or {},
        "createdAt": r.created_at,
        "completedAt": r.completed_at,
        "checks": [check_to_dict(c) for c in (r.checks or [])],
    }
