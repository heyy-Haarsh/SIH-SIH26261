"""Applicant-only views: narrow DTOs that never carry internal scrutiny data."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_roles
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.common import ApplicantApplicationOut, ApplicantApplicationSummaryOut
from app.services import applicant_view_service

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
