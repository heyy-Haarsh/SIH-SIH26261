"""Document authenticity / forensics APIs."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import NotFoundError, UnprocessableError
from app.core.security import ensure_application_access, require_roles
from app.models.application import Application
from app.models.enums import ForensicsIndicatorStatus, UserRole
from app.models.user import User
from app.schemas.common import ForensicsIndicatorOut, ForensicsResolveIn, ForensicsRunOut
from app.services import forensics_service
from app.services.serializers import forensics_indicator_to_out, forensics_run_to_out

router = APIRouter(tags=["forensics"])


@router.post(
    "/applications/{application_id}/forensics-runs",
    response_model=ForensicsRunOut,
)
def start_forensics(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.REGIONAL_OFFICER)),
):
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise NotFoundError("Application not found")
    ensure_application_access(user, app)
    forensics_service.run_forensics(
        db,
        app,
        triggered_by=user.id,
        actor_name=user.name,
        trigger="api",
        commit=True,
    )
    loaded = forensics_service.get_latest_run(db, application_id)
    if not loaded:
        raise NotFoundError("Forensics run not found after create")
    return forensics_run_to_out(loaded)


@router.get(
    "/applications/{application_id}/forensics-runs/latest",
    response_model=ForensicsRunOut | None,
)
def latest_forensics(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.REGIONAL_OFFICER)),
):
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise NotFoundError("Application not found")
    ensure_application_access(user, app)
    run = forensics_service.get_latest_run(db, application_id)
    if not run:
        return None
    return forensics_run_to_out(run)


@router.get(
    "/applications/{application_id}/forensics-indicators",
    response_model=list[ForensicsIndicatorOut],
)
def list_forensics_indicators(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.REGIONAL_OFFICER)),
):
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise NotFoundError("Application not found")
    ensure_application_access(user, app)
    return [forensics_indicator_to_out(i) for i in forensics_service.list_open_indicators(db, application_id)]


@router.post(
    "/forensics-indicators/{indicator_id}/resolve",
    response_model=ForensicsIndicatorOut,
)
def resolve_forensics_indicator(
    indicator_id: str,
    body: ForensicsResolveIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER)),
):
    try:
        status = ForensicsIndicatorStatus(body.status.strip().lower())
    except ValueError as exc:
        raise UnprocessableError("status must be one of: resolved, waived, accepted") from exc
    item = forensics_service.resolve_indicator(
        db, user, indicator_id, status=status, reason=body.reason
    )
    return forensics_indicator_to_out(item)
