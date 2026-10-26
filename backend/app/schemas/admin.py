"""Administrator configuration schemas (CamelModel outs, snake/camel inputs)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.base import CamelModel


class UserCreateIn(BaseModel):
    name: str
    email: str
    role: str
    institution_id: str | None = None
    is_active: bool = True


class UserUpdateIn(BaseModel):
    name: str | None = None
    email: str | None = None
    role: str | None = None
    institution_id: str | None = None
    is_active: bool | None = None
    change_reason: str = ""


class UserAdminOut(CamelModel):
    id: str
    name: str
    email: str
    role: str
    institution_id: str | None = None
    institution_name: str | None = None
    is_active: bool
    created_at: datetime | None = None


class InstitutionAdminOut(CamelModel):
    id: str
    name: str
    code: str
    state: str
    type: str


class CategoryDocIn(BaseModel):
    code: str
    name: str
    mandatory: bool = True
    allowed_types: list[str] = Field(default_factory=lambda: ["pdf"])


class CategoryCreateIn(BaseModel):
    code: str
    name: str
    description: str = ""
    required_documents: list[CategoryDocIn] = Field(default_factory=list)
    is_active: bool = True


class CategoryUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    required_documents: list[CategoryDocIn] | None = None
    is_active: bool | None = None
    change_reason: str = ""


class CategoryOut(CamelModel):
    id: str
    code: str
    name: str
    description: str
    required_documents: list[dict[str, Any]] = Field(default_factory=list)
    is_active: bool


class RuleCreateIn(BaseModel):
    code: str
    name: str
    description: str = ""
    handbook_ref: str = ""
    verified_source_ref: str = ""
    is_synthetic: bool = True
    definition: dict[str, Any] = Field(default_factory=dict)
    version: str = "v1"
    change_reason: str = "Initial version"
    effective_from: datetime | None = None


class RuleVersionCreateIn(BaseModel):
    version: str
    definition: dict[str, Any] = Field(default_factory=dict)
    change_reason: str
    effective_from: datetime | None = None
    publish: bool = False


class RuleUpdateIn(BaseModel):
    name: str | None = None
    description: str | None = None
    handbook_ref: str | None = None
    verified_source_ref: str | None = None
    is_active: bool | None = None
    change_reason: str = ""


class RuleVersionOut(CamelModel):
    id: str
    version: str
    definition: dict[str, Any] = Field(default_factory=dict)
    status: str
    change_reason: str = ""
    created_by_id: str | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    published_at: datetime | None = None
    created_at: datetime


class RuleOut(CamelModel):
    id: str
    rule_code: str
    name: str
    description: str
    handbook_ref: str
    verified_source_ref: str = ""
    is_synthetic: bool
    is_active: bool
    current_version: str
    versions: list[RuleVersionOut] = Field(default_factory=list)


class RuleValidateOut(CamelModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SettingOut(CamelModel):
    key: str
    value: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    updated_by_id: str | None = None
    change_reason: str = ""
    updated_at: datetime | None = None


class SettingUpdateIn(BaseModel):
    value: dict[str, Any]
    change_reason: str = ""


class AuditEventAdminOut(CamelModel):
    id: str
    action: str
    actor: str
    actor_role: str = ""
    timestamp: datetime
    detail: str
    application_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditListOut(CamelModel):
    items: list[AuditEventAdminOut]
    total: int
    limit: int
    offset: int


class AdminStatsOut(CamelModel):
    user_count: int
    active_rule_count: int
    category_count: int
    audit_events_24h: int
    live_verification_enabled: bool
