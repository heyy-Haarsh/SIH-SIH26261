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
    entity_type: str | None = None,
    entity_id: str | None = None,
    metadata: dict | None = None,
) -> AuditEvent:
    # Never persist secrets or raw document payloads in audit metadata.
    safe_meta: dict = {}
    for k, v in (metadata or {}).items():
        key = str(k).lower()
        if any(s in key for s in ("secret", "password", "token", "api_key", "content", "bytes")):
            continue
        safe_meta[k] = v
    event = AuditEvent(
        application_id=application_id,
        action=action,
        actor_name=actor,
        actor_id=actor_id,
        actor_role=actor_role,
        detail=detail,
        entity_type=entity_type,
        entity_id=entity_id,
        event_metadata=safe_meta,
    )
    db.add(event)
    db.flush()
    return event
