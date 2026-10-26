from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_roles
from app.models.audit import AuditEvent
from app.models.enums import UserRole
from app.models.rule import RegulatoryRule
from app.models.user import User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
):
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role.value if hasattr(u.role, "value") else u.role,
            "institutionId": u.institution_id,
            "isActive": u.is_active,
        }
        for u in users
    ]


@router.get("/rules")
def list_rules(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.OFFICER)),
):
    rules = db.query(RegulatoryRule).all()
    return [
        {
            "id": r.id,
            "ruleCode": r.code,
            "name": r.name,
            "description": r.description,
            "isSynthetic": r.is_synthetic,
            "versions": [
                {
                    "version": v.version,
                    "definition": v.definition,
                    "effectiveFrom": v.effective_from.isoformat() if v.effective_from else None,
                }
                for v in r.versions
            ],
        }
        for r in rules
    ]


@router.get("/audit")
def list_audit(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.ADMIN)),
    limit: int = 50,
):
    events = db.query(AuditEvent).order_by(AuditEvent.created_at.desc()).limit(limit).all()
    return [
        {
            "id": e.id,
            "action": e.action,
            "actor": e.actor_name,
            "timestamp": e.created_at.isoformat(),
            "detail": e.detail,
            "applicationId": e.application_id,
        }
        for e in events
    ]


@router.get("/jobs")
def list_jobs(_: User = Depends(require_roles(UserRole.ADMIN))):
    return {
        "backend": "local_sync",
        "celeryEnabled": False,
        "message": (
            "Async Celery workers are not required for local demo; "
            "validation runs synchronously."
        ),
        "jobs": [],
    }
