"""In-app notifications.

``notify_*`` helpers only ``db.add`` — they never commit — so a notification is stored in the same
transaction as the workflow change that caused it (and is rolled back with it). Delivery over
email/SMS is not implemented; this is an in-app inbox only.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.application import Application
from app.models.base import utcnow
from app.models.enums import UserRole
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationListOut, NotificationOut


def applicant_link(application_id: str) -> str:
    return f"/applicant/applications/{application_id}"


def officer_link(application_id: str) -> str:
    return f"/officer/applications/{application_id}"


def notify_user(
    db: Session,
    user_id: str | None,
    *,
    kind: str,
    title: str,
    body: str = "",
    application_id: str | None = None,
    link: str | None = None,
) -> None:
    if not user_id:
        return
    db.add(
        Notification(
            user_id=user_id,
            kind=kind,
            title=title[:255],
            body=body,
            application_id=application_id,
            link=link,
        )
    )


def notify_applicants(
    db: Session, app: Application, *, kind: str, title: str, body: str = ""
) -> None:
    """Every active applicant user of the application's institution gets their own copy."""
    users = (
        db.query(User.id)
        .filter(
            User.role == UserRole.APPLICANT,
            User.institution_id == app.institution_id,
            User.is_active.is_(True),
        )
        .all()
    )
    for (uid,) in users:
        notify_user(
            db,
            uid,
            kind=kind,
            title=title,
            body=body,
            application_id=app.id,
            link=applicant_link(app.id),
        )


def notify_assigned_officer(
    db: Session, app: Application, *, kind: str, title: str, body: str = ""
) -> None:
    notify_user(
        db,
        app.assigned_officer_id,
        kind=kind,
        title=title,
        body=body,
        application_id=app.id,
        link=officer_link(app.id),
    )


def _out(n: Notification) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        kind=n.kind,
        title=n.title,
        body=n.body,
        application_id=n.application_id,
        link=n.link,
        created_at=n.created_at,
        read_at=n.read_at,
        is_read=n.read_at is not None,
    )


def list_for_user(
    db: Session, user: User, *, unread_only: bool = False, limit: int = 50
) -> NotificationListOut:
    base = db.query(Notification).filter(Notification.user_id == user.id)
    unread = base.filter(Notification.read_at.is_(None)).count()
    query = base.filter(Notification.read_at.is_(None)) if unread_only else base
    rows = query.order_by(Notification.created_at.desc()).limit(max(1, min(limit, 200))).all()
    return NotificationListOut(items=[_out(n) for n in rows], unread_count=unread)


def mark_read(db: Session, user: User, notification_id: str) -> NotificationOut:
    n = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user.id)
        .first()
    )
    if n is None:
        raise NotFoundError("Notification not found.")
    if n.read_at is None:
        n.read_at = utcnow()
        db.commit()
    return _out(n)


def mark_all_read(db: Session, user: User) -> int:
    now = utcnow()
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user.id, Notification.read_at.is_(None))
        .update({Notification.read_at: now}, synchronize_session=False)
    )
    db.commit()
    return int(count or 0)
