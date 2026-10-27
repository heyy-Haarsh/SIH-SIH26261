"""Cross-document reconciliation APIs."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import NotFoundError
from app.core.security import ensure_application_access, require_roles
from app.models.application import Application
from app.models.enums import ReconciliationItemStatus, UserRole
from app.models.user import User
from app.schemas.common import (
    DiscrepancyOut,
    ReconciliationResolveIn,
    ReconciliationRunOut,
)
from app.services import reconciliation_service
from app.services.serializers import reconciliation_item_to_out, reconciliation_run_to_out

router = APIRouter(tags=["reconciliation"])


@router.post(
    "/applications/{application_id}/reconciliation-runs",
    response_model=ReconciliationRunOut,
)
def start_reconciliation(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
):
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise NotFoundError("Application not found")
    ensure_application_access(user, app)
    run = reconciliation_service.run_reconciliation(
        db,
        app,
        triggered_by=user.id,
        actor_name=user.name,
        trigger="api",
        commit=True,
    )
    # Reload with relationships
    loaded = reconciliation_service.get_latest_run(db, application_id)
    return reconciliation_run_to_out(loaded or run)


@router.get(
    "/applications/{application_id}/reconciliation-runs/latest",
    response_model=ReconciliationRunOut | None,
)
def latest_reconciliation(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
):
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise NotFoundError("Application not found")
    ensure_application_access(user, app)
    run = reconciliation_service.get_latest_run(db, application_id)
    if not run:
        return None
    return reconciliation_run_to_out(run)


@router.get(
    "/applications/{application_id}/reconciliation-items",
    response_model=list[DiscrepancyOut],
)
def list_reconciliation_items(
    application_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER, UserRole.ADMIN)),
):
    app = db.query(Application).filter(Application.id == application_id).first()
    if not app:
        raise NotFoundError("Application not found")
    ensure_application_access(user, app)
    items = reconciliation_service.list_open_items_for_application(db, application_id)
    return [reconciliation_item_to_out(i) for i in items]


@router.post(
    "/reconciliation-items/{item_id}/resolve",
    response_model=DiscrepancyOut,
)
def resolve_reconciliation_item(
    item_id: str,
    body: ReconciliationResolveIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.OFFICER)),
):
    try:
        status = ReconciliationItemStatus(body.status.strip().lower())
    except ValueError as exc:
        from app.core.errors import UnprocessableError

        raise UnprocessableError(
            "status must be one of: resolved, waived, accepted"
        ) from exc
    item = reconciliation_service.resolve_item(
        db, user, item_id, status=status, reason=body.reason
    )
    return reconciliation_item_to_out(item)
