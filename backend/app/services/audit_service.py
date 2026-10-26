from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


def record_audit(
    db: Session,
    *,
    action: str,
    actor: str,
    detail: str = "",
    application_id: str | None = None,
    actor_id: str | None = None,
    actor_role: str = "system",
) -> AuditEvent:
    event = AuditEvent(
        application_id=application_id,
        action=action,
        actor_name=actor,
        actor_id=actor_id,
        actor_role=actor_role,
        detail=detail,
    )
    db.add(event)
    db.flush()
    return event
