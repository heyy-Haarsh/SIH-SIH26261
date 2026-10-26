"""Administrator configuration & audit APIs (admin-only unless noted)."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_roles
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.admin import (
    CategoryCreateIn,
    CategoryUpdateIn,
    RuleCreateIn,
    RuleUpdateIn,
    RuleVersionCreateIn,
    SettingUpdateIn,
    UserCreateIn,
    UserUpdateIn,
)
from app.services import admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return admin_service.admin_stats(db, user)


@router.get("/institutions")
def list_institutions(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return [
        {
            "id": i.id,
            "name": i.name,
            "code": i.code,
            "state": i.state,
            "type": i.type,
        }
        for i in admin_service.list_institutions(db, user)
    ]


# ---- users ------------------------------------------------------------------


@router.get("/users")
def list_users(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return [admin_service.user_to_dict(u) for u in admin_service.list_users(db, user)]


@router.post("/users", status_code=201)
def create_user(
    body: UserCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return admin_service.user_to_dict(admin_service.create_user(db, user, body.model_dump()))


@router.patch("/users/{user_id}")
def update_user(
    user_id: str,
    body: UserUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return admin_service.user_to_dict(
        admin_service.update_user(db, user, user_id, body.model_dump(exclude_unset=True))
    )


@router.post("/users/{user_id}/deactivate")
def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
    reason: str = Query("Deactivated by administrator", min_length=3),
):
    return admin_service.user_to_dict(
        admin_service.deactivate_user(db, user, user_id, change_reason=reason)
    )


# ---- categories -------------------------------------------------------------


@router.get("/categories")
def list_categories(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.OFFICER)),
    only_active: bool = False,
):
    return [
        admin_service.category_to_dict(c)
        for c in admin_service.list_categories(db, user, only_active=only_active)
    ]


@router.post("/categories", status_code=201)
def create_category(
    body: CategoryCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    data = body.model_dump()
    data["required_documents"] = [d if isinstance(d, dict) else d.model_dump() for d in body.required_documents]
    return admin_service.category_to_dict(admin_service.create_category(db, user, data))


@router.patch("/categories/{category_id}")
def update_category(
    category_id: str,
    body: CategoryUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    data = body.model_dump(exclude_unset=True)
    if "required_documents" in data and data["required_documents"] is not None:
        data["required_documents"] = [
            d if isinstance(d, dict) else d for d in data["required_documents"]
        ]
    return admin_service.category_to_dict(
        admin_service.update_category(db, user, category_id, data)
    )


# ---- rules ------------------------------------------------------------------


@router.get("/rules")
def list_rules(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN, UserRole.OFFICER)),
    only_active: bool = False,
    synthetic: Optional[bool] = None,
):
    return [
        admin_service.rule_to_dict(r)
        for r in admin_service.list_rules(db, user, only_active=only_active, synthetic=synthetic)
    ]


@router.post("/rules/validate")
def validate_rule(
    body: RuleCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return admin_service.preview_validate_rule(db, user, body.model_dump())


@router.post("/rules", status_code=201)
def create_rule(
    body: RuleCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return admin_service.rule_to_dict(admin_service.create_rule(db, user, body.model_dump()))


@router.patch("/rules/{rule_id}")
def update_rule(
    rule_id: str,
    body: RuleUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return admin_service.rule_to_dict(
        admin_service.update_rule_meta(db, user, rule_id, body.model_dump(exclude_unset=True))
    )


@router.post("/rules/{rule_id}/versions", status_code=201)
def create_rule_version(
    rule_id: str,
    body: RuleVersionCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return admin_service.rule_to_dict(
        admin_service.create_rule_version(
            db,
            user,
            rule_id,
            version=body.version,
            definition=body.definition,
            change_reason=body.change_reason,
            effective_from=body.effective_from,
            publish=body.publish,
        )
    )


@router.post("/rules/{rule_id}/versions/{version}/publish")
def publish_rule_version(
    rule_id: str,
    version: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
    reason: str = Query("", max_length=500),
):
    return admin_service.rule_to_dict(
        admin_service.publish_rule_version(db, user, rule_id, version, change_reason=reason)
    )


@router.post("/rules/{rule_id}/versions/{version}/reactivate")
def reactivate_rule_version(
    rule_id: str,
    version: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
    reason: str = Query(..., min_length=5, max_length=500),
):
    return admin_service.rule_to_dict(
        admin_service.reactivate_rule_version(db, user, rule_id, version, change_reason=reason)
    )


# ---- settings ---------------------------------------------------------------


@router.get("/settings")
def list_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return [admin_service.setting_to_dict(s) for s in admin_service.list_settings(db, user)]


@router.get("/settings/{key}")
def get_setting(
    key: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return admin_service.setting_to_dict(admin_service.get_setting(db, key, create_default=True))


@router.put("/settings/{key}")
def update_setting(
    key: str,
    body: SettingUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
):
    return admin_service.setting_to_dict(
        admin_service.update_setting(
            db, user, key, value=body.value, change_reason=body.change_reason
        )
    )


# ---- audit ------------------------------------------------------------------


@router.get("/audit")
def list_audit(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.ADMIN)),
    action: Optional[str] = None,
    actor: Optional[str] = None,
    application_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    items, total = admin_service.search_audit(
        db,
        user,
        action=action,
        actor=actor,
        application_id=application_id,
        entity_type=entity_type,
        q=q,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return {
        "items": [admin_service.audit_event_to_dict(e) for e in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


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
