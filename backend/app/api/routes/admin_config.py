"""Category configuration APIs (administrator only).

Categories are the primary workflow: information fields, document requirements, rules and
publishing all hang off a category. ``/rules/overview`` is only a filtered, cross-category view
over the same rules, not a second rule store.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.errors import NotFoundError
from app.core.security import require_roles
from app.models.category import ApplicationCategory
from app.models.category_config import CategoryConfigVersion, DocumentRequirement
from app.models.enums import UserRole
from app.models.user import User
from app.rules import definition as rd
from app.services import category_config_service as ccs

router = APIRouter(prefix="/admin/config", tags=["admin-config"])

Admin = Depends(require_roles(UserRole.REGIONAL_OFFICER))


class CategoryCreateIn(BaseModel):
    code: str
    name: str
    description: str = ""


class CategoryUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class InfoFieldsIn(BaseModel):
    fields: list[dict[str, Any]] = Field(default_factory=list)


class PublishIn(BaseModel):
    note: str = ""


class RequirementIn(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    mandatory: Optional[bool] = None
    allowed_types: Optional[list[str]] = None
    max_size_mb: Optional[int] = None
    expected_fields: Optional[list[str]] = None
    document_type_code: Optional[str] = None
    is_active: Optional[bool] = None
    acknowledge_impact: bool = False


class OrderIn(BaseModel):
    ids: list[str]


class RuleIn(BaseModel):
    title: str = ""
    description: str = ""
    definition: Any = None  # a JSON object, or JSON text
    authoring_mode: str = "json"  # json | plain
    natural_language: str = ""
    source_reference: str = ""
    notes: str = ""
    change_summary: str = ""


class ActivateIn(BaseModel):
    confirm_interpretation: bool = False


class ValidateIn(BaseModel):
    definition: Any = None
    source_reference: str = ""
    requirement_id: Optional[str] = None


class SuggestIn(BaseModel):
    text: str


class DryRunIn(BaseModel):
    definition: Any = None
    source_reference: str = ""
    sample: dict[str, Any] = Field(default_factory=dict)


# ---- categories -------------------------------------------------------------------------
@router.get("/categories")
def list_categories(
    q: str = "",
    status: str = "",
    state: str = Query("", description="published | unpublished_changes | unpublished"),
    db: Session = Depends(get_db),
    user: User = Admin,
):
    return ccs.list_categories(db, user, q=q, status=status, state=state)


@router.post("/categories", status_code=201)
def create_category(body: CategoryCreateIn, db: Session = Depends(get_db), user: User = Admin):
    cat = ccs.create_category(db, user, code=body.code, name=body.name, description=body.description)
    return ccs.category_detail(db, user, cat.id)


@router.get("/categories/{category_id}")
def get_category(category_id: str, db: Session = Depends(get_db), user: User = Admin):
    return ccs.category_detail(db, user, category_id)


@router.patch("/categories/{category_id}")
def update_category(category_id: str, body: CategoryUpdateIn, db: Session = Depends(get_db), user: User = Admin):
    ccs.update_category_meta(
        db, user, category_id, name=body.name, description=body.description, is_active=body.is_active
    )
    return ccs.category_detail(db, user, category_id)


@router.put("/categories/{category_id}/info-fields")
def put_info_fields(category_id: str, body: InfoFieldsIn, db: Session = Depends(get_db), user: User = Admin):
    ccs.set_info_fields(db, user, category_id, body.fields)
    return ccs.category_detail(db, user, category_id)


@router.get("/categories/{category_id}/validation")
def validate_category(category_id: str, db: Session = Depends(get_db), user: User = Admin):
    cat = db.get(ApplicationCategory, category_id)
    if cat is None:
        raise NotFoundError("Category not found.")
    return {"validation": ccs.validate_configuration(db, cat), "pendingChanges": ccs.pending_changes(db, cat)}


@router.post("/categories/{category_id}/publish")
def publish_category(category_id: str, body: PublishIn, db: Session = Depends(get_db), user: User = Admin):
    ccs.publish(db, user, category_id, note=body.note)
    return ccs.category_detail(db, user, category_id)


@router.get("/categories/{category_id}/versions/{version}")
def get_version(category_id: str, version: int, db: Session = Depends(get_db), user: User = Admin):
    row = (
        db.query(CategoryConfigVersion)
        .filter(CategoryConfigVersion.category_id == category_id, CategoryConfigVersion.version == version)
        .first()
    )
    if row is None:
        raise NotFoundError("Configuration version not found.")
    return {
        "id": row.id,
        "version": row.version,
        "status": row.status,
        "summary": row.summary,
        "publishedAt": row.published_at.isoformat() if row.published_at else None,
        "snapshot": row.snapshot,
    }


# ---- requirements -----------------------------------------------------------------------
@router.post("/categories/{category_id}/requirements", status_code=201)
def create_requirement(category_id: str, body: RequirementIn, db: Session = Depends(get_db), user: User = Admin):
    data = body.model_dump(exclude_unset=True, exclude={"acknowledge_impact", "is_active"})
    req = ccs.create_requirement(db, user, category_id, data)
    return ccs.requirement_to_dict(db, req)


@router.put("/categories/{category_id}/requirements/order")
def reorder_requirements(category_id: str, body: OrderIn, db: Session = Depends(get_db), user: User = Admin):
    ccs.reorder_requirements(db, user, category_id, body.ids)
    return ccs.category_detail(db, user, category_id)


@router.patch("/requirements/{requirement_id}")
def update_requirement(requirement_id: str, body: RequirementIn, db: Session = Depends(get_db), user: User = Admin):
    data = body.model_dump(exclude_unset=True, exclude={"acknowledge_impact"})
    req, impact = ccs.update_requirement(db, user, requirement_id, data, acknowledge_impact=body.acknowledge_impact)
    return {**ccs.requirement_to_dict(db, req), "impact": impact}


@router.get("/requirements/{requirement_id}/impact")
def requirement_impact(requirement_id: str, db: Session = Depends(get_db), user: User = Admin):
    req = db.get(DocumentRequirement, requirement_id)
    if req is None:
        raise NotFoundError("Requirement not found.")
    return ccs.requirement_impact(db, req)


# ---- rules ------------------------------------------------------------------------------
@router.get("/requirements/{requirement_id}/rules")
def list_requirement_rules(requirement_id: str, db: Session = Depends(get_db), user: User = Admin):
    return ccs.requirement_rules(db, user, requirement_id)


@router.post("/requirements/{requirement_id}/rules", status_code=201)
def create_rule(requirement_id: str, body: RuleIn, db: Session = Depends(get_db), user: User = Admin):
    rule = ccs.create_rule(db, user, requirement_id, body.model_dump())
    return ccs.rule_detail(db, user, rule.id)


@router.post("/requirements/{requirement_id}/rules/dry-run")
def dry_run_rule(requirement_id: str, body: DryRunIn, db: Session = Depends(get_db), user: User = Admin):
    return ccs.dry_run(
        db, user, requirement_id, definition=body.definition, source_reference=body.source_reference, sample=body.sample
    )


@router.get("/rules/overview")
def rules_overview(
    category_id: str = "",
    requirement_id: str = "",
    status: str = "",
    rule_type: str = "",
    config_version: Optional[int] = None,
    db: Session = Depends(get_db),
    user: User = Admin,
):
    return ccs.rules_overview(
        db, user, category_id=category_id, requirement_id=requirement_id, status=status,
        rule_type=rule_type, config_version=config_version,
    )


@router.get("/rules/{rule_id}")
def get_rule(rule_id: str, db: Session = Depends(get_db), user: User = Admin):
    return ccs.rule_detail(db, user, rule_id)


@router.put("/rules/{rule_id}/draft")
def save_rule_draft(rule_id: str, body: RuleIn, db: Session = Depends(get_db), user: User = Admin):
    ccs.save_rule_draft(db, user, rule_id, body.model_dump())
    return ccs.rule_detail(db, user, rule_id)


@router.delete("/rules/{rule_id}/draft")
def discard_rule_draft(rule_id: str, db: Session = Depends(get_db), user: User = Admin):
    ccs.discard_rule_draft(db, user, rule_id)
    return {"ok": True}


@router.post("/rules/{rule_id}/edit")
def edit_rule(rule_id: str, db: Session = Depends(get_db), user: User = Admin):
    ccs.edit_active_rule(db, user, rule_id)
    return ccs.rule_detail(db, user, rule_id)


@router.post("/rules/{rule_id}/versions/{version}/activate")
def activate_rule(rule_id: str, version: int, body: ActivateIn, db: Session = Depends(get_db), user: User = Admin):
    ccs.activate_rule_version(db, user, rule_id, version, confirm_interpretation=body.confirm_interpretation)
    return ccs.rule_detail(db, user, rule_id)


@router.post("/rules/{rule_id}/deactivate")
def deactivate_rule(rule_id: str, db: Session = Depends(get_db), user: User = Admin):
    ccs.deactivate_rule(db, user, rule_id)
    return ccs.rule_detail(db, user, rule_id)


@router.post("/rules/{rule_id}/duplicate", status_code=201)
def duplicate_rule(rule_id: str, db: Session = Depends(get_db), user: User = Admin):
    rule = ccs.duplicate_rule(db, user, rule_id)
    return ccs.rule_detail(db, user, rule.id)


# ---- definition tooling -----------------------------------------------------------------
@router.post("/rule-definitions/validate")
def validate_definition(body: ValidateIn, db: Session = Depends(get_db), user: User = Admin):
    requirement = db.get(DocumentRequirement, body.requirement_id) if body.requirement_id else None
    return ccs.validate_rule_input(
        definition=body.definition, source_reference=body.source_reference, requirement=requirement
    )


@router.post("/rule-definitions/suggest")
def suggest_definition(body: SuggestIn, user: User = Admin):
    """A *proposal* only. Nothing is saved or executed; the administrator must review and activate."""
    out = rd.suggest_from_text(body.text)
    if out["definition"] is not None:
        out["explanation"] = rd.explain(out["definition"])
        out["validation"] = rd.validate_definition(out["definition"], source_reference="").to_dict()
    return out


@router.get("/rule-definitions/schema")
def definition_schema(user: User = Admin):
    return {
        "schemaVersion": rd.SCHEMA_VERSION,
        "checkTypes": [
            {"type": s.type, "label": s.label, "params": list(s.params), "required": list(s.required), "needsSource": s.needs_source}
            for s in rd.CHECK_TYPES.values()
        ],
        "operators": list(rd.OPERATORS),
        "formats": list(rd.FORMAT_NAMES),
        "valueTypes": list(rd.VALUE_TYPES),
        "onFail": list(rd.ON_FAIL_VALUES),
        "knownFields": rd.known_fields(),
        "example": {
            "schema_version": rd.SCHEMA_VERSION,
            "check": {"type": "field_present", "field": "certificate_number"},
            "on_fail": "warning",
        },
    }
