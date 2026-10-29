"""Applicant-only views: narrow DTOs that never carry internal scrutiny data."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_roles
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import (
    ApplicantApplicationOut,
    ApplicantApplicationSummaryOut,
    ApplicantDeficiencyOut,
    ApplicantEvidenceOut,
    ApplicantOverviewOut,
)
from app.services import applicant_view_service
from app.services import demo_documents_service

router = APIRouter(prefix="/applicant", tags=["applicant"])


@router.get("/applications", response_model=list[ApplicantApplicationSummaryOut])
def list_my_applications(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.APPLICANT)),
):
    return applicant_view_service.list_applicant_applications(db, user)


@router.get("/applications/{application_id}", response_model=ApplicantApplicationOut)
def get_my_application(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.APPLICANT)),
):
    return applicant_view_service.get_applicant_application(db, user, application_id)


@router.post("/applications/{application_id}/demo-documents")
def attach_demo_documents(
    application_id: str,
    include_optional: bool = Query(default=True),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.APPLICANT)),
):
    """Demo helper: fill every empty checklist slot with synthetic / test-image files."""
    result = demo_documents_service.attach_demo_documents(
        db, user, application_id, include_optional=include_optional
    )
    app = applicant_view_service.get_applicant_application(db, user, application_id)
    return {**result, "application": app}


@router.get("/overview", response_model=ApplicantOverviewOut)
def get_overview(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.APPLICANT)),
):
    """Dashboard counts, next actions and recent activity — one server-side definition."""
    return applicant_view_service.applicant_overview(db, user)


@router.get("/clarifications", response_model=list[ApplicantDeficiencyOut])
def list_clarifications(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.APPLICANT)),
):
    return applicant_view_service.list_clarifications(db, user)


@router.get("/findings/{finding_id}/evidence", response_model=ApplicantEvidenceOut)
def get_finding_evidence(
    finding_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.APPLICANT)),
):
    """Evidence for one applicant-visible finding. Anything else is a 404, not a 403."""
    return applicant_view_service.finding_evidence(db, user, finding_id)
