"""Administrator configuration & audit APIs (admin-only unless noted)."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_roles
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.admin import (
    CategoryCreateIn,
    CategoryUpdateIn,
    IntegrationToggleIn,
    RuleDraftIn,
    RuleImportIn,
    RuleCreateIn,
    RuleUpdateIn,
    RuleVersionCreateIn,
    SettingUpdateIn,
    UserCreateIn,
    UserUpdateIn,
)
from app.schemas.scrutiny import HandbookReferenceIn
from app.core.errors import UnprocessableError
from app.services import (
    admin_service,
    integration_service,
    rule_import_service,
    system_health_service,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def get_stats(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    return admin_service.admin_stats(db, user)


@router.get("/institutions")
def list_institutions(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
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
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    return [admin_service.user_to_dict(u) for u in admin_service.list_users(db, user)]


@router.post("/users", status_code=201)
def create_user(
    body: UserCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    return admin_service.user_to_dict(admin_service.create_user(db, user, body.model_dump()))


@router.patch("/users/{user_id}")
def update_user(
    user_id: str,
    body: UserUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    return admin_service.user_to_dict(
        admin_service.update_user(db, user, user_id, body.model_dump(exclude_unset=True))
    )


@router.post("/users/{user_id}/deactivate")
def deactivate_user(
    user_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
    reason: str = Query("Deactivated by administrator", min_length=3),
):
    return admin_service.user_to_dict(
        admin_service.deactivate_user(db, user, user_id, change_reason=reason)
    )


# ---- categories -------------------------------------------------------------


@router.get("/categories")
def list_categories(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER, UserRole.OFFICER)),
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
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    data = body.model_dump()
    data["required_documents"] = [d if isinstance(d, dict) else d.model_dump() for d in body.required_documents]
    return admin_service.category_to_dict(admin_service.create_category(db, user, data))


@router.patch("/categories/{category_id}")
def update_category(
    category_id: str,
    body: CategoryUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
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
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER, UserRole.OFFICER)),
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
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    return admin_service.preview_validate_rule(db, user, body.model_dump())


@router.post("/rules", status_code=201)
def create_rule(
    body: RuleCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    return admin_service.rule_to_dict(admin_service.create_rule(db, user, body.model_dump()))


@router.patch("/rules/{rule_id}")
def update_rule(
    rule_id: str,
    body: RuleUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    return admin_service.rule_to_dict(
        admin_service.update_rule_meta(db, user, rule_id, body.model_dump(exclude_unset=True))
    )


@router.post("/rules/{rule_id}/versions", status_code=201)
def create_rule_version(
    rule_id: str,
    body: RuleVersionCreateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
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
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
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
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
    reason: str = Query(..., min_length=5, max_length=500),
):
    return admin_service.rule_to_dict(
        admin_service.reactivate_rule_version(db, user, rule_id, version, change_reason=reason)
    )


# ---- settings ---------------------------------------------------------------


@router.get("/settings")
def list_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    return [admin_service.setting_to_dict(s) for s in admin_service.list_settings(db, user)]


@router.get("/settings/{key}")
def get_setting(
    key: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    return admin_service.setting_to_dict(admin_service.get_setting(db, key, create_default=True))


@router.put("/settings/{key}")
def update_setting(
    key: str,
    body: SettingUpdateIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
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
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
    action: Optional[str] = None,
    category: Optional[str] = None,
    actor: Optional[str] = None,
    actor_role: Optional[str] = None,
    application_id: Optional[str] = None,
    application_number: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
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
        category=category,
        actor=actor,
        actor_role=actor_role,
        application_id=application_id,
        application_number=application_number,
        entity_type=entity_type,
        entity_id=entity_id,
        q=q,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
        offset=offset,
    )
    return {
        "items": admin_service.audit_events_to_dicts(db, items),
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/audit/facets")
def audit_facets(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    return admin_service.audit_facets(db, user)


def _csv_cell(value: object) -> str:
    text = "" if value is None else str(value)
    # Neutralise spreadsheet formula injection from user-controlled text.
    if text[:1] in ("=", "+", "-", "@", "\t", "\r"):
        text = "'" + text
    return text


@router.get("/audit/export.csv")
def export_audit_csv(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
    action: Optional[str] = None,
    category: Optional[str] = None,
    actor: Optional[str] = None,
    actor_role: Optional[str] = None,
    application_id: Optional[str] = None,
    application_number: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
):
    import csv
    import io
    import json

    filters = dict(
        action=action,
        category=category,
        actor=actor,
        actor_role=actor_role,
        application_id=application_id,
        application_number=application_number,
        entity_type=entity_type,
        entity_id=entity_id,
        q=q,
        date_from=date_from,
        date_to=date_to,
    )
    rows = admin_service.audit_export_rows(db, user, **filters)
    dicts = admin_service.audit_events_to_dicts(db, rows, full=True)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["timestamp", "action", "category", "actor", "actor_role", "application_number",
         "entity_type", "entity_id", "detail", "metadata"]
    )
    for d in dicts:
        writer.writerow(
            [
                _csv_cell(d["timestamp"].isoformat() if d["timestamp"] else ""),
                _csv_cell(d["action"]),
                _csv_cell(d["category"]),
                _csv_cell(d["actor"]),
                _csv_cell(d["actorRole"]),
                _csv_cell(d["applicationNumber"]),
                _csv_cell(d["entityType"]),
                _csv_cell(d["entityId"]),
                _csv_cell(d["detail"]),
                _csv_cell(json.dumps(d["metadata"], default=str, sort_keys=True)),
            ]
        )
    from app.services.audit_service import record_audit

    record_audit(
        db,
        action="admin.audit_exported",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=f"rows={len(dicts)}",
        entity_type="audit_export",
        metadata={"rows": len(dicts), "filters": {k: str(v) for k, v in filters.items() if v}},
    )
    db.commit()
    return Response(
        content="\ufeff" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="praman-audit-log.csv"'},
    )


@router.get("/audit/{event_id}")
def get_audit_event(
    event_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    return admin_service.audit_event_detail(db, user, event_id)


@router.get("/jobs")
def list_jobs(_: User = Depends(require_roles(UserRole.REGIONAL_OFFICER))):
    return {
        "backend": "local_sync",
        "celeryEnabled": False,
        "message": (
            "Async Celery workers are not required for local demo; "
            "validation runs synchronously."
        ),
        "jobs": [],
    }


@router.get("/audit-chain/verify")
def verify_audit_chain(
    from_seq: Optional[int] = Query(None),
    to_seq: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    _ = user
    from app.services.audit_chain_service import verify_chain_integrity

    result = verify_chain_integrity(db, from_seq=from_seq, to_seq=to_seq)
    return {
        "ok": result.ok,
        "checked": result.checked,
        "firstBadSequence": result.first_bad_sequence,
        "detail": result.detail,
    }


# ---- handbook references (verified citations only) ------------------------------------


@router.get("/handbook-references")
def list_handbook_references(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    from app.services import handbook_service

    _ = user
    return [r.model_dump(by_alias=True, mode="json") for r in handbook_service.list_references(db)]


@router.put("/handbook-references")
def upsert_handbook_reference(
    body: HandbookReferenceIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    from app.services import handbook_service

    return handbook_service.upsert_reference(db, user, body).model_dump(by_alias=True, mode="json")


@router.delete("/handbook-references/{reference_id}")
def delete_handbook_reference(
    reference_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    from app.services import handbook_service

    handbook_service.delete_reference(db, user, reference_id)
    return {"ok": True}



# ---- rule import & drafting (never activates anything) -----------------------------


@router.post("/rules/import/validate")
def validate_rule_import(
    body: RuleImportIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    items, file_errors = rule_import_service.parse_payload(body.json_text, body.rules)
    results = rule_import_service.validate_items(db, items) if not file_errors or items else []
    valid = not file_errors and bool(results) and all(r["valid"] for r in results)
    return {
        "valid": valid,
        "fileErrors": file_errors,
        "results": results,
        "willCreate": sum(1 for r in results if r["valid"]),
        "note": "Validation only. Importing saves drafts; nothing is activated.",
    }


@router.post("/rules/import", status_code=201)
def import_rules(
    body: RuleImportIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    items, file_errors = rule_import_service.parse_payload(body.json_text, body.rules)
    if file_errors:
        raise UnprocessableError(" ".join(file_errors), code="rule_import_invalid", extra={"fileErrors": file_errors})
    return rule_import_service.import_items(db, user, items, origin="json_import")


@router.post("/rules/draft-from-text")
def draft_rule_from_text(
    body: RuleDraftIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    return rule_import_service.draft_from_text(db, body.text)


@router.post("/rules/drafts", status_code=201)
def save_rule_draft(
    body: RuleImportIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    items, file_errors = rule_import_service.parse_payload(body.json_text, body.rules)
    if file_errors:
        raise UnprocessableError(" ".join(file_errors), code="rule_import_invalid", extra={"fileErrors": file_errors})
    return rule_import_service.import_items(db, user, items, origin="natural_language")


@router.post("/rules/{rule_id}/versions/{version}/discard")
def discard_rule_draft(
    rule_id: str,
    version: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
    reason: str = Query(..., min_length=3, max_length=500),
):
    return admin_service.rule_to_dict(
        admin_service.discard_draft_version(db, user, rule_id, version, change_reason=reason)
    )


@router.get("/rules/{rule_id}/usage")
def rule_usage(
    rule_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    return admin_service.rule_usage(db, user, rule_id)


# ---- integrations & system health ------------------------------------------------------


@router.get("/integrations")
def list_integrations(_: User = Depends(require_roles(UserRole.REGIONAL_OFFICER))):
    items = integration_service.list_integrations()
    return {"items": items, "summary": integration_service.summarize(items)}


@router.get("/integrations/{integration_id}")
def get_integration(integration_id: str, _: User = Depends(require_roles(UserRole.REGIONAL_OFFICER))):
    return integration_service.get_integration(integration_id)


@router.put("/integrations/{integration_id}")
def toggle_integration(
    integration_id: str,
    body: IntegrationToggleIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    return integration_service.set_integration_enabled(
        db, user, integration_id, enabled=body.enabled, reason=body.reason
    )


@router.post("/integrations/{integration_id}/check")
def check_integration(
    integration_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    result = integration_service.check_integration(integration_id)
    from app.services.audit_service import record_audit

    record_audit(
        db,
        action="admin.integration_checked",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=f"{integration_id}: {(result.get('lastCheck') or {}).get('message', '')}",
        entity_type="integration",
        metadata={"integration": integration_id, "result": result.get("lastCheck")},
    )
    db.commit()
    return result


@router.get("/system-health")
def get_system_health(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    return system_health_service.system_health(db)


# ---- delegation (Regional Officer) ------------------------------------------


@router.get("/officers")
def list_officers_with_load(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    from app.services import delegation_service

    return delegation_service.list_officers_with_load(db, user)


@router.get("/officers/{officer_id}/queue")
def get_officer_queue(
    officer_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    from app.services import delegation_service
    from app.services.serializers import application_summary

    apps = delegation_service.officer_queue(db, user, officer_id)
    return [application_summary(db, a) for a in apps]


@router.get("/delegation/queue")
def get_delegation_queue(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    from app.services import delegation_service
    from app.services.serializers import application_summary

    apps = delegation_service.unassigned_queue(db, user)
    return [application_summary(db, a) for a in apps]


@router.post("/applications/{application_id}/delegate")
def delegate_application(
    application_id: str,
    body: dict | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    from app.services import delegation_service
    from app.services.serializers import application_summary

    payload = body or {}
    officer_id = payload.get("officerId") or payload.get("officer_id")
    app = delegation_service.delegate(db, user, application_id, officer_id=officer_id)
    return application_summary(db, app)


@router.post("/applications/bulk-delegate")
def bulk_delegate_applications(
    body: dict | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    from app.services import delegation_service

    payload = body or {}
    ids = payload.get("applicationIds") or payload.get("application_ids")
    return {"results": delegation_service.bulk_delegate(db, user, ids)}


@router.get("/delegation/settings")
def get_delegation_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    from app.services import delegation_service

    return delegation_service.get_weights(db)


@router.put("/delegation/settings")
def update_delegation_settings(
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.REGIONAL_OFFICER)),
):
    from app.services import delegation_service

    return delegation_service.set_weights(db, user, body)
