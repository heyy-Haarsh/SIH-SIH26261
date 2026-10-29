from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.notification import NotificationListOut, NotificationOut
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListOut)
def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """The caller's own in-app notifications (never anyone else's)."""
    return notification_service.list_for_user(db, user, unread_only=unread_only, limit=limit)


@router.post("/read-all")
def read_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {"marked": notification_service.mark_all_read(db, user)}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def read_one(
    notification_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return notification_service.mark_read(db, user, notification_id)
