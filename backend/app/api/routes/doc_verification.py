"""Phase 7 document verification APIs."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_roles
from app.models.enums import UserRole
from app.models.user import User
from app.services import doc_verification_service as svc

router = APIRouter(tags=["document-verification"])


class ResolveCheckIn(BaseModel):
    status: str = Field(..., description="resolved | waived | accepted")
    reason: str


@router.get("/document-verification/configs")
def get_configs(user: User = Depends(require_roles(UserRole.OFFICER, UserRole.REGIONAL_OFFICER))):
    _ = user
    return svc.list_engine_configs()


@router.post("/applications/{application_id}/document-verification")
def run_app_verification(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.REGIONAL_OFFICER)),
):
    runs = svc.run_application_pipeline(db, user, application_id)
    return [svc.run_to_dict(r) for r in runs]


@router.get("/applications/{application_id}/document-verification")
def list_app_verification(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.REGIONAL_OFFICER)),
):
    runs = svc.list_runs_for_application(db, user, application_id)
    return [svc.run_to_dict(r) for r in runs]


@router.post("/documents/{document_id}/document-verification")
def run_doc_verification(
    document_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.REGIONAL_OFFICER)),
):
    run = svc.run_document_pipeline(db, user, document_id)
    return svc.run_to_dict(run)


@router.get("/document-verification-runs/{run_id}")
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.REGIONAL_OFFICER)),
):
    return svc.run_to_dict(svc.get_run(db, user, run_id))


@router.post("/document-verification-checks/{check_id}/resolve")
def resolve_check(
    check_id: str,
    body: ResolveCheckIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER)),
):
    check = svc.resolve_check(db, user, check_id, status=body.status, reason=body.reason)
    return svc.check_to_dict(check)
