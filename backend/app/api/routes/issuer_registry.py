"""Issuer registry APIs — live authenticity verify against stored issuer records."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_roles
from app.models.enums import UserRole
from app.models.user import User
from app.services import issuer_registry_service as svc

router = APIRouter(prefix="/issuer-registry", tags=["issuer-registry"])


@router.get("/records")
def list_registry_records(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.REGIONAL_OFFICER, UserRole.APPLICANT)),
):
    """List seeded / registered issuer documents (demo catalogue)."""
    return {"records": svc.list_records(db, user)}


@router.post("/verify")
def verify_against_registry(
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.REGIONAL_OFFICER, UserRole.APPLICANT)),
):
    """Live verify: OCR-derived certificate fields vs issuer registry.

    This is the endpoint to show in a demo Network tab.
    """
    return svc.verify(db, user, body or {})


@router.post("/documents/{document_id}/verify")
def verify_document(
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.REGIONAL_OFFICER, UserRole.APPLICANT)),
):
    """Build payload from the document's extracted fields, then hit the same verify logic."""
    return svc.verify_document(db, user, document_id)


@router.get("/documents/{document_id}/verify-payload")
def preview_verify_payload(
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.REGIONAL_OFFICER, UserRole.APPLICANT)),
):
    """Show what would be sent to /verify (for the demo video before clicking)."""
    return svc.build_verify_payload_from_document(db, document_id, user)


@router.get("/events")
def list_verify_events(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.REGIONAL_OFFICER)),
):
    return {"events": svc.recent_events(db, user)}
