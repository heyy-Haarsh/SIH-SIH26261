"""Scrutiny-officer review endpoints: grouped issues, per-document pipeline, file preview."""

from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import NotFoundError
from app.core.security import ensure_application_access, get_current_user, require_roles
from app.models.application import Application
from app.models.document import Document
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.scrutiny import DocumentReportOut, ScrutinyReviewOut
from app.services import document_report_service, scrutiny_view_service

router = APIRouter(tags=["scrutiny"])

_officer = require_roles(UserRole.OFFICER, UserRole.ADMIN)


def _app(db: Session, application_id: str) -> Application:
    app = db.get(Application, application_id)
    if app is None:
        raise NotFoundError("Application not found.")
    return app


@router.get("/applications/{application_id}/scrutiny-review", response_model=ScrutinyReviewOut)
def get_scrutiny_review(
    application_id: str, db: Session = Depends(get_db), user: User = Depends(_officer)
):
    return scrutiny_view_service.build_review(db, _app(db, application_id))


@router.get(
    "/applications/{application_id}/documents/{document_id}/report",
    response_model=DocumentReportOut,
)
def get_document_report(
    application_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(_officer),
):
    return document_report_service.build_document_report(db, _app(db, application_id), document_id)


@router.get("/documents/{document_id}/file")
def get_document_file(
    document_id: str,
    version: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Serve the stored file for preview. Applicants may only open their own institution's files."""
    doc = db.get(Document, document_id)
    if doc is None:
        raise NotFoundError("Document not found.")
    app = _app(db, doc.application_id)
    ensure_application_access(user, app)
    versions = {v.version: v for v in doc.versions}
    chosen = versions.get(version) if version is not None else doc.latest_version
    if chosen is None:
        raise NotFoundError("Document version not found.")
    path = Path(chosen.storage_path).resolve()
    root = get_settings().upload_path.resolve()
    if root not in path.parents or not path.is_file():
        raise NotFoundError("The stored file is no longer available.")
    return FileResponse(
        path,
        media_type=chosen.mime_type or "application/octet-stream",
        filename=chosen.file_name,
        content_disposition_type="inline",
        headers={"X-Content-Type-Options": "nosniff"},
    )
