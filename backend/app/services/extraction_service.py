"""Application service for document extraction runs."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.security import ensure_application_access
from app.document_processing.orchestrator import run_extraction_for_version
from app.document_processing.ocr_processor import tesseract_status
from app.models.application import Application
from app.models.document import Document, DocumentVersion, ExtractedField
from app.models.enums import UserRole
from app.models.extraction import ExtractionRun
from app.models.user import User
from app.services.audit_service import record_audit
from app.services.validation_service import run_validation


def _get_document_for_user(db: Session, user: User, document_id: str) -> Document:
    doc = (
        db.query(Document)
        .options(joinedload(Document.versions), joinedload(Document.application))
        .filter(Document.id == document_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    ensure_application_access(user, doc.application)
    return doc


def start_extraction(
    db: Session,
    user: User,
    document_id: str,
    *,
    force: bool = False,
    run_validation_after: bool = True,
) -> ExtractionRun:
    if user.role not in (UserRole.APPLICANT, UserRole.OFFICER, UserRole.REGIONAL_OFFICER):
        raise HTTPException(status_code=403, detail="Insufficient role")

    doc = _get_document_for_user(db, user, document_id)
    version = doc.latest_version
    if not version:
        raise HTTPException(status_code=400, detail="Document has no uploaded version")

    run = run_extraction_for_version(
        db,
        version,
        application_id=doc.application_id,
        selected_requirement_code=doc.requirement_code,
        triggered_by_id=user.id,
        force=force,
    )
    record_audit(
        db,
        action="extraction.run_completed",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=f"Extraction {run.id} status={run.status.value}",
        application_id=doc.application_id,
    )

    if run_validation_after and run.status.value.startswith("completed"):
        app = db.query(Application).filter(Application.id == doc.application_id).one()
        validation = run_validation(db, app, triggered_by=user.id, actor_name=user.name)
        run.validation_run_id = validation.id
        db.add(run)
        db.commit()
        db.refresh(run)
    else:
        db.commit()
        db.refresh(run)
    return run


def get_extraction_run(db: Session, user: User, run_id: str) -> ExtractionRun:
    run = db.query(ExtractionRun).filter(ExtractionRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Extraction run not found")
    app = db.query(Application).filter(Application.id == run.application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    ensure_application_access(user, app)
    return run


def get_latest_extraction_for_document(
    db: Session, user: User, document_id: str
) -> ExtractionRun | None:
    doc = _get_document_for_user(db, user, document_id)
    version = doc.latest_version
    if not version:
        return None
    return (
        db.query(ExtractionRun)
        .filter(ExtractionRun.document_version_id == version.id)
        .order_by(ExtractionRun.created_at.desc())
        .first()
    )


def list_fields_for_run(db: Session, run_id: str) -> list[ExtractedField]:
    return (
        db.query(ExtractedField)
        .filter(ExtractedField.extraction_run_id == run_id)
        .order_by(ExtractedField.field_name)
        .all()
    )


def correct_field(
    db: Session,
    user: User,
    field_id: str,
    *,
    corrected_value: str,
) -> ExtractedField:
    if user.role not in (UserRole.OFFICER, UserRole.REGIONAL_OFFICER):
        raise HTTPException(status_code=403, detail="Only officers can correct extracted fields")
    field = db.query(ExtractedField).filter(ExtractedField.id == field_id).first()
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    app = db.query(Application).filter(Application.id == field.application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    ensure_application_access(user, app)
    from app.models.enums import FieldReviewStatus

    field.corrected_value = corrected_value
    field.review_status = FieldReviewStatus.CORRECTED
    db.add(field)
    record_audit(
        db,
        action="extraction.field_corrected",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=f"Corrected field {field.field_name}",
        application_id=field.application_id,
    )
    db.commit()
    db.refresh(field)
    return field


def ocr_capability() -> dict:
    return tesseract_status()
