from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import ensure_application_access, get_current_user, require_roles
from app.models.application import Application
from app.models.enums import UserRole
from app.models.user import User
from app.models.validation import Finding
from app.schemas.common import (
    ApplicationCreateIn,
    ApplicationDetailOut,
    ApplicationSummaryOut,
    UploadResultOut,
    ValidationRunOut,
)
from app.services import application_service, document_service
from app.services.serializers import finding_to_out
from app.services.validation_service import run_validation

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationSummaryOut])
def list_applications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return application_service.list_applications(db, user)


@router.post("", response_model=ApplicationDetailOut)
def create_application(
    body: ApplicationCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.APPLICANT)),
):
    return application_service.create_application(
        db,
        user,
        category_code=body.category_code,
        program_name=body.program_name,
        academic_year=body.academic_year,
    )


@router.get("/{application_id}", response_model=ApplicationDetailOut)
def get_application(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return application_service.get_application(db, user, application_id)


@router.post("/{application_id}/documents", response_model=UploadResultOut)
async def upload_document(
    application_id: str,
    requirement_code: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.APPLICANT, UserRole.ADMIN)),
):
    return document_service.upload_document(
        db,
        user,
        application_id,
        file=file,
        requirement_code=requirement_code,
    )


@router.post("/{application_id}/validation-runs", response_model=ValidationRunOut)
def create_validation_run(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(
        require_roles(UserRole.APPLICANT, UserRole.OFFICER, UserRole.ADMIN)
    ),
):
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    ensure_application_access(user, app)
    run = run_validation(db, app, triggered_by=user.id, actor_name=user.name)
    findings = db.query(Finding).filter(Finding.validation_run_id == run.id).all()
    for f in findings:
        _ = f.evidence
    status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
    return ValidationRunOut(
        validation_run_id=run.id,
        status=status_val,
        findings=[finding_to_out(f) for f in findings],
    )
