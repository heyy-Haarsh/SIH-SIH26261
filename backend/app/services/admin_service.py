"""Administrator configuration: users, categories, rules, settings, audit search."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.errors import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.models.audit import AuditEvent
from app.models.category import ApplicationCategory
from app.models.enums import UserRole
from app.models.rule import RegulatoryRule, RuleVersion
from app.models.settings import SystemSetting
from app.models.user import Institution, User
from app.services import application_metrics_service
from app.services.audit_service import record_audit

# Logic keys understood by the synthetic rule engine / seed definitions.
KNOWN_LOGIC_KEYS = frozenset(
    {
        "missing_mandatory",
        "filename_contains_expired",
        "params",
        "description",
        "synthetic",
        "logic",
        "min_confidence",
        "required_fields",
        "max_days_expired",
        "source_text",
        "draft_origin",
    }
)

# `logic` values the shipped engine understands (see app.rules.engine and core.seed).
KNOWN_LOGIC_VALUES = frozenset({"missing_mandatory", "filename_contains_expired", "cross_identity"})

SENSITIVE_SETTING_KEYS = frozenset(
    {"secret_key", "llm_api_key", "aicte_api_key", "sarvam_api_key", "password", "token", "api_key"}
)

DEFAULT_VERIFICATION_SETTINGS: dict[str, Any] = {
    "enableLiveVerification": False,
    "preferSimulatedAdapters": True,
    "requireManualReviewOnUnavailable": True,
    "maxConcurrentVerificationRequests": 5,
    "note": "Live government connectors stay off until authorized credentials are configured.",
}

DEFAULT_UPLOAD_SETTINGS: dict[str, Any] = {
    "maxUploadMb": 25,
    "allowedExtensions": ["pdf", "png", "jpg", "jpeg", "docx", "txt"],
    "autoExtractOnUpload": True,
}


def _require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN:
        raise ForbiddenError("Administrator role required.")


def _parse_role(value: str) -> UserRole:
    try:
        return UserRole(value.strip().lower())
    except ValueError as exc:
        raise UnprocessableError(
            f"Invalid role '{value}'. Allowed: applicant, officer, admin."
        ) from exc


def _scrub_metadata(meta: dict | None) -> dict:
    """Never expose secrets or raw document contents in admin audit responses."""
    if not meta:
        return {}
    out: dict[str, Any] = {}
    for k, v in meta.items():
        key = str(k).lower()
        if any(s in key for s in ("secret", "password", "token", "api_key", "content", "bytes")):
            out[k] = "[redacted]"
        elif isinstance(v, str) and len(v) > 500:
            out[k] = v[:500] + "…"
        else:
            out[k] = v
    return out


# ---- stats ------------------------------------------------------------------


def admin_stats(db: Session, user: User) -> dict[str, Any]:
    _require_admin(user)
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
    return {
        "userCount": db.query(User).count(),
        "activeRuleCount": db.query(RegulatoryRule).filter(RegulatoryRule.is_active.is_(True)).count(),
        "categoryCount": db.query(ApplicationCategory).count(),
        "auditEvents24h": db.query(AuditEvent).filter(AuditEvent.created_at >= since).count(),
        # Deployment flag is the single source of truth (the admin setting cannot exceed it).
        "liveVerificationEnabled": bool(settings.enable_live_verification),
        # Same function the officer dashboard uses, so both screens always agree.
        "applications": application_metrics_service.application_metrics(db),
    }


# ---- users ------------------------------------------------------------------


def list_institutions(db: Session, user: User) -> list[Institution]:
    _require_admin(user)
    return db.query(Institution).order_by(Institution.name).all()


def list_users(db: Session, user: User) -> list[User]:
    _require_admin(user)
    return (
        db.query(User)
        .options(joinedload(User.institution))
        .order_by(User.role, User.name)
        .all()
    )


def create_user(db: Session, actor: User, data: dict[str, Any]) -> User:
    _require_admin(actor)
    email = (data.get("email") or "").strip().lower()
    name = (data.get("name") or "").strip()
    if not email or "@" not in email:
        raise UnprocessableError("A valid email is required.")
    if len(name) < 2:
        raise UnprocessableError("Name is required.")
    if db.query(User).filter(User.email == email).first():
        raise ConflictError("A user with this email already exists.")
    role = _parse_role(data.get("role") or "applicant")
    institution_id = data.get("institution_id")
    if role == UserRole.APPLICANT and not institution_id:
        raise UnprocessableError("Applicants must be linked to an institution.")
    if institution_id and not db.get(Institution, institution_id):
        raise UnprocessableError("Institution not found.")
    u = User(
        name=name,
        email=email,
        role=role,
        institution_id=institution_id,
        is_active=bool(data.get("is_active", True)),
    )
    db.add(u)
    db.flush()
    record_audit(
        db,
        action="admin.user_created",
        actor=actor.name,
        actor_id=actor.id,
        actor_role=actor.role.value,
        detail=f"user={u.email}; role={u.role.value}",
        entity_type="user",
        entity_id=u.id,
    )
    db.commit()
    db.refresh(u)
    return u


def update_user(db: Session, actor: User, user_id: str, data: dict[str, Any]) -> User:
    _require_admin(actor)
    u = db.get(User, user_id)
    if not u:
        raise NotFoundError("User not found")
    reason = (data.get("change_reason") or "").strip()
    changes: list[str] = []
    if data.get("name") is not None:
        name = str(data["name"]).strip()
        if len(name) < 2:
            raise UnprocessableError("Name is required.")
        if name != u.name:
            changes.append(f"name:{u.name}->{name}")
            u.name = name
    if data.get("email") is not None:
        email = str(data["email"]).strip().lower()
        if "@" not in email:
            raise UnprocessableError("A valid email is required.")
        other = db.query(User).filter(User.email == email, User.id != u.id).first()
        if other:
            raise ConflictError("A user with this email already exists.")
        if email != u.email:
            changes.append(f"email:{u.email}->{email}")
            u.email = email
    if data.get("role") is not None:
        role = _parse_role(str(data["role"]))
        if role != u.role:
            changes.append(f"role:{u.role.value}->{role.value}")
            u.role = role
    if "institution_id" in data:
        institution_id = data.get("institution_id")
        if institution_id and not db.get(Institution, institution_id):
            raise UnprocessableError("Institution not found.")
        if institution_id != u.institution_id:
            changes.append(f"institution:{u.institution_id}->{institution_id}")
            u.institution_id = institution_id
    if data.get("is_active") is not None:
        active = bool(data["is_active"])
        if active != u.is_active:
            changes.append(f"active:{u.is_active}->{active}")
            u.is_active = active
    if u.role == UserRole.APPLICANT and not u.institution_id:
        raise UnprocessableError("Applicants must be linked to an institution.")
    if u.id == actor.id and data.get("is_active") is False:
        raise UnprocessableError("You cannot deactivate your own admin account.")
    if changes and len(reason) < 3:
        raise UnprocessableError("change_reason (≥3 chars) is required when modifying a user.")
    record_audit(
        db,
        action="admin.user_updated",
        actor=actor.name,
        actor_id=actor.id,
        actor_role=actor.role.value,
        detail="; ".join(changes) + (f"; reason={reason}" if reason else ""),
        entity_type="user",
        entity_id=u.id,
    )
    db.commit()
    db.refresh(u)
    return u


def deactivate_user(db: Session, actor: User, user_id: str, *, change_reason: str) -> User:
    return update_user(
        db,
        actor,
        user_id,
        {"is_active": False, "change_reason": change_reason or "Deactivated by administrator"},
    )


# ---- categories -------------------------------------------------------------


def _normalize_docs(docs: list[dict] | None) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for raw in docs or []:
        code = str(raw.get("code") or "").strip().upper()
        name = str(raw.get("name") or "").strip()
        if not code or not name:
            raise UnprocessableError("Each document requirement needs code and name.")
        if code in seen:
            raise UnprocessableError(f"Duplicate document requirement code: {code}")
        seen.add(code)
        allowed = raw.get("allowed_types") or ["pdf"]
        if not isinstance(allowed, list) or not allowed:
            raise UnprocessableError(f"allowed_types required for {code}")
        out.append(
            {
                "code": code,
                "name": name,
                "mandatory": bool(raw.get("mandatory", True)),
                "allowed_types": [str(t).lower().lstrip(".") for t in allowed],
            }
        )
    return out


def list_categories(db: Session, user: User, *, only_active: bool = False) -> list[ApplicationCategory]:
    if user.role not in (UserRole.ADMIN, UserRole.OFFICER):
        raise ForbiddenError("Insufficient permissions.")
    q = db.query(ApplicationCategory).order_by(ApplicationCategory.code)
    if only_active:
        q = q.filter(ApplicationCategory.is_active.is_(True))
    return q.all()


def create_category(db: Session, actor: User, data: dict[str, Any]) -> ApplicationCategory:
    _require_admin(actor)
    code = (data.get("code") or "").strip().upper()
    name = (data.get("name") or "").strip()
    if not re.match(r"^[A-Z0-9_-]{2,64}$", code):
        raise UnprocessableError("Category code must be 2–64 chars: A-Z, 0-9, _, -.")
    if len(name) < 2:
        raise UnprocessableError("Category name is required.")
    if db.query(ApplicationCategory).filter(ApplicationCategory.code == code).first():
        raise ConflictError(f"Category code already exists: {code}")
    cat = ApplicationCategory(
        code=code,
        name=name,
        description=(data.get("description") or "").strip(),
        required_documents=_normalize_docs(data.get("required_documents")),
        is_active=bool(data.get("is_active", True)),
    )
    db.add(cat)
    db.flush()
    record_audit(
        db,
        action="admin.category_created",
        actor=actor.name,
        actor_id=actor.id,
        actor_role=actor.role.value,
        detail=f"code={cat.code}; docs={len(cat.required_documents)}",
        entity_type="category",
        entity_id=cat.id,
    )
    db.commit()
    db.refresh(cat)
    return cat


def update_category(db: Session, actor: User, category_id: str, data: dict[str, Any]) -> ApplicationCategory:
    _require_admin(actor)
    cat = db.get(ApplicationCategory, category_id)
    if not cat:
        raise NotFoundError("Category not found")
    reason = (data.get("change_reason") or "").strip()
    changes: list[str] = []
    if data.get("name") is not None:
        name = str(data["name"]).strip()
        if len(name) < 2:
            raise UnprocessableError("Category name is required.")
        if name != cat.name:
            changes.append("name")
            cat.name = name
    if data.get("description") is not None:
        cat.description = str(data["description"]).strip()
        changes.append("description")
    if data.get("required_documents") is not None:
        cat.required_documents = _normalize_docs(data["required_documents"])
        changes.append(f"docs={len(cat.required_documents)}")
    if data.get("is_active") is not None:
        cat.is_active = bool(data["is_active"])
        changes.append(f"active={cat.is_active}")
    if changes and len(reason) < 3:
        raise UnprocessableError("change_reason (≥3 chars) is required when modifying a category.")
    record_audit(
        db,
        action="admin.category_updated",
        actor=actor.name,
        actor_id=actor.id,
        actor_role=actor.role.value,
        detail="; ".join(changes) + (f"; reason={reason}" if reason else ""),
        entity_type="category",
        entity_id=cat.id,
    )
    db.commit()
    db.refresh(cat)
    return cat


# ---- rules ------------------------------------------------------------------


def validate_rule_definition(
    *,
    code: str,
    is_synthetic: bool,
    handbook_ref: str,
    verified_source_ref: str,
    definition: dict[str, Any],
    existing_codes: set[str] | None = None,
    ignore_code: str | None = None,
) -> tuple[bool, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    code = (code or "").strip().upper()
    if not re.match(r"^[A-Z0-9_-]{3,64}$", code):
        errors.append("rule code must be 3–64 chars: A-Z, 0-9, _, -.")
    if existing_codes and code in existing_codes and code != (ignore_code or "").upper():
        errors.append(f"duplicate rule identifier: {code}")
    if not isinstance(definition, dict):
        errors.append("definition must be a JSON object.")
        return False, errors, warnings
    if not definition:
        errors.append("definition is empty — provide logic/params.")
    logic = definition.get("logic")
    if logic is not None and not isinstance(logic, str):
        errors.append("definition.logic must be a string when present.")
    unknown = [k for k in definition.keys() if k not in KNOWN_LOGIC_KEYS]
    if unknown:
        warnings.append(f"Unrecognized definition keys (kept but unused by engine): {', '.join(unknown)}")
    if "params" in definition and not isinstance(definition["params"], dict):
        errors.append("definition.params must be an object.")
    params = definition.get("params")
    if code == "SYN-RULE-003" and isinstance(params, dict):
        days = params.get("warn_within_days")
        if days is not None and (isinstance(days, bool) or not isinstance(days, int) or days < 0 or days > 3650):
            errors.append("params.warn_within_days must be a whole number of days between 0 and 3650.")
        kws = params.get("filename_keywords")
        if kws is not None and (
            not isinstance(kws, list) or not kws or not all(isinstance(k, str) and k.strip() for k in kws)
        ):
            errors.append("params.filename_keywords must be a non-empty list of words.")
        extra = sorted(set(params) - {"warn_within_days", "filename_keywords"})
        if extra:
            warnings.append(f"SYN-RULE-003 ignores these params: {', '.join(extra)}.")
    if logic is not None and isinstance(logic, str) and logic not in KNOWN_LOGIC_VALUES:
        warnings.append(
            f"logic '{logic}' is not implemented by the rule engine; this rule is recorded as documentation only."
        )
    if "required_fields" in definition and not isinstance(definition["required_fields"], list):
        errors.append("definition.required_fields must be a list.")
    if "min_confidence" in definition:
        try:
            mc = float(definition["min_confidence"])
            if not 0 <= mc <= 1:
                errors.append("min_confidence must be between 0 and 1.")
        except (TypeError, ValueError):
            errors.append("min_confidence must be a number.")
    # Official vs synthetic
    if not is_synthetic:
        if not (verified_source_ref or "").strip():
            errors.append(
                "Official rules require verified_source_ref citing verified source material. "
                "Do not invent AICTE clauses."
            )
        if not (handbook_ref or "").strip():
            errors.append("Official rules require handbook_ref from verified source material.")
        lower = (handbook_ref or "").lower() + " " + (verified_source_ref or "").lower()
        if "placeholder" in lower or "demo" in lower or "synthetic" in lower:
            errors.append(
                "Official rules cannot use demo/placeholder/synthetic citations — "
                "configure only from verified source material."
            )
        if code.startswith("SYN-"):
            errors.append("Official rules should not use SYN-* codes reserved for synthetic demos.")
    else:
        if not code.startswith("SYN-") and "SYNTHETIC" not in (definition.get("description") or ""):
            warnings.append("Synthetic demo rules should prefer SYN-* codes for clarity.")
    return len(errors) == 0, errors, warnings


def list_rules(
    db: Session,
    user: User,
    *,
    only_active: bool = False,
    synthetic: bool | None = None,
) -> list[RegulatoryRule]:
    if user.role not in (UserRole.ADMIN, UserRole.OFFICER):
        raise ForbiddenError("Insufficient permissions.")
    q = (
        db.query(RegulatoryRule)
        .options(joinedload(RegulatoryRule.versions))
        .order_by(RegulatoryRule.code)
    )
    if only_active:
        q = q.filter(RegulatoryRule.is_active.is_(True))
    if synthetic is not None:
        q = q.filter(RegulatoryRule.is_synthetic.is_(synthetic))
    return q.all()


def create_rule(db: Session, actor: User, data: dict[str, Any]) -> RegulatoryRule:
    _require_admin(actor)
    code = (data.get("code") or "").strip().upper()
    name = (data.get("name") or "").strip()
    is_synthetic = bool(data.get("is_synthetic", True))
    handbook_ref = (data.get("handbook_ref") or "").strip()
    verified_source_ref = (data.get("verified_source_ref") or "").strip()
    definition = dict(data.get("definition") or {})
    version = (data.get("version") or "v1").strip()
    change_reason = (data.get("change_reason") or "Initial version").strip()
    if len(name) < 3:
        raise UnprocessableError("Rule name is required.")
    existing = {r.code for r in db.query(RegulatoryRule).all()}
    ok, errors, _warnings = validate_rule_definition(
        code=code,
        is_synthetic=is_synthetic,
        handbook_ref=handbook_ref,
        verified_source_ref=verified_source_ref,
        definition=definition,
        existing_codes=existing,
    )
    if not ok:
        raise UnprocessableError("; ".join(errors))
    if is_synthetic and "SYNTHETIC" not in name.upper():
        name = f"[SYNTHETIC] {name}"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    rule = RegulatoryRule(
        code=code,
        name=name,
        description=(data.get("description") or "").strip(),
        handbook_ref=handbook_ref
        or ("Demo handbook (placeholder — not official AICTE APH)" if is_synthetic else ""),
        verified_source_ref=verified_source_ref,
        is_synthetic=is_synthetic,
        is_active=True,
        current_version=version,
    )
    rule.versions.append(
        RuleVersion(
            version=version,
            definition=definition,
            status="published",
            change_reason=change_reason,
            created_by_id=actor.id,
            effective_from=data.get("effective_from") or now,
            published_at=now,
        )
    )
    db.add(rule)
    db.flush()
    record_audit(
        db,
        action="admin.rule_created",
        actor=actor.name,
        actor_id=actor.id,
        actor_role=actor.role.value,
        detail=f"code={code}; version={version}; synthetic={is_synthetic}; reason={change_reason}",
        entity_type="rule",
        entity_id=rule.id,
    )
    db.commit()
    return (
        db.query(RegulatoryRule)
        .options(joinedload(RegulatoryRule.versions))
        .filter(RegulatoryRule.id == rule.id)
        .one()
    )


def update_rule_meta(db: Session, actor: User, rule_id: str, data: dict[str, Any]) -> RegulatoryRule:
    _require_admin(actor)
    rule = db.get(RegulatoryRule, rule_id)
    if not rule:
        raise NotFoundError("Rule not found")
    reason = (data.get("change_reason") or "").strip()
    changes: list[str] = []
    if data.get("name") is not None:
        rule.name = str(data["name"]).strip()
        changes.append("name")
    if data.get("description") is not None:
        rule.description = str(data["description"]).strip()
        changes.append("description")
    if data.get("handbook_ref") is not None:
        rule.handbook_ref = str(data["handbook_ref"]).strip()
        changes.append("handbook_ref")
    if data.get("verified_source_ref") is not None:
        rule.verified_source_ref = str(data["verified_source_ref"]).strip()
        changes.append("verified_source_ref")
    if data.get("is_active") is not None:
        rule.is_active = bool(data["is_active"])
        changes.append(f"active={rule.is_active}")
    if not rule.is_synthetic:
        ok, errors, _ = validate_rule_definition(
            code=rule.code,
            is_synthetic=False,
            handbook_ref=rule.handbook_ref,
            verified_source_ref=rule.verified_source_ref,
            definition={"logic": "noop"},
        )
        # Re-validate source fields only (ignore empty definition noise)
        src_errors = [e for e in errors if "verified_source" in e or "handbook_ref" in e or "placeholder" in e]
        if src_errors:
            raise UnprocessableError("; ".join(src_errors))
    if changes and len(reason) < 3:
        raise UnprocessableError("change_reason (≥3 chars) is required.")
    record_audit(
        db,
        action="admin.rule_updated",
        actor=actor.name,
        actor_id=actor.id,
        actor_role=actor.role.value,
        detail="; ".join(changes) + f"; reason={reason}",
        entity_type="rule",
        entity_id=rule.id,
    )
    db.commit()
    return (
        db.query(RegulatoryRule)
        .options(joinedload(RegulatoryRule.versions))
        .filter(RegulatoryRule.id == rule.id)
        .one()
    )


def create_rule_version(
    db: Session,
    actor: User,
    rule_id: str,
    *,
    version: str,
    definition: dict[str, Any],
    change_reason: str,
    effective_from: datetime | None = None,
    publish: bool = False,
) -> RegulatoryRule:
    """Append a new version — never mutate prior RuleVersion rows used in past scrutiny runs."""
    _require_admin(actor)
    rule = (
        db.query(RegulatoryRule)
        .options(joinedload(RegulatoryRule.versions))
        .filter(RegulatoryRule.id == rule_id)
        .first()
    )
    if not rule:
        raise NotFoundError("Rule not found")
    version = (version or "").strip()
    change_reason = (change_reason or "").strip()
    if not version:
        raise UnprocessableError("version is required.")
    if len(change_reason) < 5:
        raise UnprocessableError("change_reason (≥5 chars) is required for new versions.")
    if any(v.version == version for v in rule.versions):
        raise ConflictError(f"Version '{version}' already exists for this rule — choose a new version id.")
    ok, errors, _warnings = validate_rule_definition(
        code=rule.code,
        is_synthetic=rule.is_synthetic,
        handbook_ref=rule.handbook_ref,
        verified_source_ref=rule.verified_source_ref,
        definition=definition or {},
    )
    if not ok:
        raise UnprocessableError("; ".join(errors))
    status = "published" if publish else "draft"
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    previous_current = rule.current_version
    # Append via relationship so delete-orphan cascade does not drop the new row.
    rv = RuleVersion(
        version=version,
        definition=dict(definition or {}),
        status=status,
        change_reason=change_reason,
        created_by_id=actor.id,
        # Activation always takes effect immediately; drafts have no effective date yet.
        effective_from=now if publish else None,
        published_at=now if publish else None,
    )
    rule.versions.append(rv)
    db.flush()
    if publish:
        _retire_other_published(rule, keep=rv, now=now)
        rule.current_version = version
        rule.is_active = True
    record_audit(
        db,
        action="admin.rule_version_created",
        actor=actor.name,
        actor_id=actor.id,
        actor_role=actor.role.value,
        detail=f"code={rule.code}; version={version}; status={status}; reason={change_reason}",
        entity_type="rule_version",
        entity_id=rv.id,
        metadata={
            "ruleCode": rule.code,
            "version": version,
            "status": status,
            "previousCurrentVersion": previous_current,
            "definition": dict(definition or {}),
            "reason": change_reason,
        },
    )
    db.commit()
    db.expire_all()
    return (
        db.query(RegulatoryRule)
        .options(joinedload(RegulatoryRule.versions))
        .filter(RegulatoryRule.id == rule_id)
        .one()
    )


def publish_rule_version(
    db: Session, actor: User, rule_id: str, version: str, *, change_reason: str = ""
) -> RegulatoryRule:
    _require_admin(actor)
    rule = (
        db.query(RegulatoryRule)
        .options(joinedload(RegulatoryRule.versions))
        .filter(RegulatoryRule.id == rule_id)
        .first()
    )
    if not rule:
        raise NotFoundError("Rule not found")
    target = next((v for v in rule.versions if v.version == version), None)
    if not target:
        raise NotFoundError("Rule version not found")
    ok, errors, _ = validate_rule_definition(
        code=rule.code,
        is_synthetic=rule.is_synthetic,
        handbook_ref=rule.handbook_ref,
        verified_source_ref=rule.verified_source_ref,
        definition=target.definition or {},
    )
    if not ok:
        raise UnprocessableError(f"Cannot publish invalid configuration: {'; '.join(errors)}")
    if target.status == "published" and rule.current_version == target.version and rule.is_active:
        raise ConflictError(f"Version '{version}' is already the active version of {rule.code}.")
    if (target.status or "") == "discarded":
        raise UnprocessableError("A discarded draft cannot be activated. Create a new version instead.")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    previous_current = rule.current_version
    was_status = target.status
    _retire_other_published(rule, keep=target, now=now)
    target.status = "published"
    target.published_at = now
    # A (re)activated version starts a fresh effective window; history of past windows is kept
    # on the findings themselves (each finding stores the rule version that produced it).
    target.effective_from = now
    target.effective_to = None
    if change_reason:
        target.change_reason = f"{target.change_reason}; published: {change_reason}".strip("; ")
    rule.current_version = target.version
    rule.is_active = True
    record_audit(
        db,
        action="admin.rule_version_published",
        actor=actor.name,
        actor_id=actor.id,
        actor_role=actor.role.value,
        detail=(
            f"code={rule.code}; version={version}; previous={previous_current}; "
            f"reason={change_reason or 'publish'}"
        ),
        entity_type="rule_version",
        entity_id=target.id,
        metadata={
            "ruleCode": rule.code,
            "version": version,
            "previousCurrentVersion": previous_current,
            "versionStatusBefore": was_status,
            "reason": change_reason or "publish",
        },
    )
    db.commit()
    return (
        db.query(RegulatoryRule)
        .options(joinedload(RegulatoryRule.versions))
        .filter(RegulatoryRule.id == rule.id)
        .one()
    )


def reactivate_rule_version(
    db: Session, actor: User, rule_id: str, version: str, *, change_reason: str
) -> RegulatoryRule:
    """Roll current pointer back to an older published version without deleting history."""
    change_reason = (change_reason or "").strip()
    if len(change_reason) < 5:
        raise UnprocessableError("change_reason (≥5 chars) required to reactivate a prior version.")
    return publish_rule_version(db, actor, rule_id, version, change_reason=f"reactivate: {change_reason}")


def _retire_other_published(rule: RegulatoryRule, *, keep: RuleVersion, now: datetime) -> None:
    """Mark every other published version retired. Rows are kept; only their status/window change."""
    for prev in rule.versions:
        if prev is keep or prev.id == keep.id:
            continue
        if (prev.status or "published") == "published":
            prev.status = "retired"
            if prev.effective_to is None:
                prev.effective_to = now


def discard_draft_version(
    db: Session, actor: User, rule_id: str, version: str, *, change_reason: str
) -> RegulatoryRule:
    """Withdraw a draft that was never activated. Published/retired versions can never be discarded."""
    _require_admin(actor)
    change_reason = (change_reason or "").strip()
    if len(change_reason) < 3:
        raise UnprocessableError("A reason (at least 3 characters) is required.")
    rule = (
        db.query(RegulatoryRule)
        .options(joinedload(RegulatoryRule.versions))
        .filter(RegulatoryRule.id == rule_id)
        .first()
    )
    if not rule:
        raise NotFoundError("Rule not found")
    target = next((v for v in rule.versions if v.version == version), None)
    if not target:
        raise NotFoundError("Rule version not found")
    if (target.status or "") != "draft":
        raise UnprocessableError("Only an unactivated draft can be discarded; activated versions are history.")
    target.status = "discarded"
    target.change_reason = f"{target.change_reason}; discarded: {change_reason}".strip("; ")
    record_audit(
        db,
        action="admin.rule_version_discarded",
        actor=actor.name,
        actor_id=actor.id,
        actor_role=actor.role.value,
        detail=f"code={rule.code}; version={version}; reason={change_reason}",
        entity_type="rule_version",
        entity_id=target.id,
        metadata={"ruleCode": rule.code, "version": version, "reason": change_reason},
    )
    db.commit()
    return (
        db.query(RegulatoryRule)
        .options(joinedload(RegulatoryRule.versions))
        .filter(RegulatoryRule.id == rule.id)
        .one()
    )


def rule_usage(db: Session, user: User, rule_id: str) -> dict[str, Any]:
    """How many recorded findings each version of a rule has produced (history is never rewritten)."""
    if user.role not in (UserRole.ADMIN, UserRole.OFFICER):
        raise ForbiddenError("Insufficient permissions.")
    from sqlalchemy import func

    from app.models.validation import Finding

    rule = db.get(RegulatoryRule, rule_id)
    if not rule:
        raise NotFoundError("Rule not found")
    rows = (
        db.query(Finding.rule_version, func.count(Finding.id))
        .filter(Finding.rule_code == rule.code)
        .group_by(Finding.rule_version)
        .all()
    )
    return {
        "ruleCode": rule.code,
        "currentVersion": rule.current_version,
        "findingsByVersion": {(v or "unversioned"): n for v, n in rows},
        "note": "Past findings keep the rule version that produced them; activating a new version only affects future runs.",
    }


def preview_validate_rule(db: Session, actor: User, data: dict[str, Any]) -> dict[str, Any]:
    _require_admin(actor)
    existing = {r.code for r in db.query(RegulatoryRule).all()}
    ok, errors, warnings = validate_rule_definition(
        code=str(data.get("code") or ""),
        is_synthetic=bool(data.get("is_synthetic", True)),
        handbook_ref=str(data.get("handbook_ref") or ""),
        verified_source_ref=str(data.get("verified_source_ref") or ""),
        definition=dict(data.get("definition") or {}),
        existing_codes=existing,
        ignore_code=data.get("ignore_code"),
    )
    return {"valid": ok, "errors": errors, "warnings": warnings}


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def active_rule_runtimes(db: Session) -> tuple[dict[str, Any], set[str]]:
    """Return (code→RuleRuntime overlays, disabled codes) for the evaluation engine.

    Only ``published`` versions inside their effective window are used; drafts, retired and
    discarded versions never reach the engine.
    """
    from app.rules.engine import RuleRuntime

    now = datetime.now(timezone.utc)
    rules = (
        db.query(RegulatoryRule)
        .options(joinedload(RegulatoryRule.versions))
        .all()
    )
    out: dict[str, RuleRuntime] = {}
    disabled: set[str] = set()
    for rule in rules:
        if not rule.is_active:
            disabled.add(rule.code)
            continue
        published = [
            v
            for v in rule.versions
            if (getattr(v, "status", None) or "published") == "published"
            and (_aware(v.effective_from) is None or _aware(v.effective_from) <= now)
            and (_aware(getattr(v, "effective_to", None)) is None or _aware(v.effective_to) > now)
        ]
        if not published:
            # Fall back to the current_version pointer for seeded rows that predate lifecycle
            # status — but never to a draft/retired/discarded row.
            published = [
                v
                for v in rule.versions
                if v.version == rule.current_version
                and (getattr(v, "status", None) or "published") == "published"
            ]
        if not published:
            continue
        published.sort(key=lambda v: _aware(v.created_at) or now, reverse=True)
        ver = published[0]
        params = dict((ver.definition or {}).get("params") or {})
        if "logic" in (ver.definition or {}):
            params = {**params, "logic": ver.definition["logic"]}
        out[rule.code] = RuleRuntime(version=ver.version, params=params)
    return out, disabled

# ---- settings ---------------------------------------------------------------


def get_setting(db: Session, key: str, *, create_default: bool = False) -> SystemSetting:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row:
        return row
    if not create_default:
        raise NotFoundError(f"Setting not found: {key}")
    defaults = {
        "verification": (
            DEFAULT_VERIFICATION_SETTINGS,
            "External verification toggles (no secrets). Live connectors stay off by default.",
        ),
        "uploads": (
            DEFAULT_UPLOAD_SETTINGS,
            "Upload limits and allowed extensions (non-secret).",
        ),
    }
    if key not in defaults:
        raise NotFoundError(f"Setting not found: {key}")
    value, desc = defaults[key]
    row = SystemSetting(key=key, value=dict(value), description=desc, change_reason="default")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_settings(db: Session, user: User) -> list[SystemSetting]:
    _require_admin(user)
    for key in ("verification", "uploads"):
        get_setting(db, key, create_default=True)
    return (
        db.query(SystemSetting)
        .filter(SystemSetting.key != "integrations")
        .order_by(SystemSetting.key)
        .all()
    )


def update_setting(
    db: Session, actor: User, key: str, *, value: dict[str, Any], change_reason: str
) -> SystemSetting:
    _require_admin(actor)
    if key.lower() in SENSITIVE_SETTING_KEYS or any(
        s in key.lower() for s in ("secret", "password", "token", "api_key")
    ):
        raise UnprocessableError("Secrets cannot be stored or modified through this API.")
    change_reason = (change_reason or "").strip()
    if len(change_reason) < 3:
        raise UnprocessableError("change_reason (≥3 chars) is required.")
    if not isinstance(value, dict):
        raise UnprocessableError("value must be a JSON object.")
    # Reject secret-looking nested keys
    for k in value.keys():
        lk = str(k).lower()
        if any(s in lk for s in ("secret", "password", "token", "api_key", "credential")):
            raise UnprocessableError(f"Refusing to store sensitive field '{k}' in settings.")
    if key == "integrations":
        raise UnprocessableError(
            "Integration switches are managed from the Integrations screen, not as a raw setting."
        )
    value = validate_setting_value(key, value)
    row = get_setting(db, key, create_default=True)
    before = dict(row.value or {})
    row.value = value
    row.updated_by_id = actor.id
    row.change_reason = change_reason
    changed = sorted(k for k in set(before) | set(value) if before.get(k) != value.get(k))
    record_audit(
        db,
        action="admin.setting_updated",
        actor=actor.name,
        actor_id=actor.id,
        actor_role=actor.role.value,
        detail=f"key={key}; changed={', '.join(changed) or 'nothing'}; reason={change_reason}",
        entity_type="system_setting",
        entity_id=row.id,
        metadata={
            "key": key,
            "changedFields": changed,
            "before": {k: before.get(k) for k in changed},
            "after": {k: value.get(k) for k in changed},
            "reason": change_reason,
        },
    )
    db.commit()
    db.refresh(row)
    from app.core import runtime_config

    runtime_config.load_from_db(db)
    return row


_VERIFICATION_KEYS = {
    "enableLiveVerification": bool,
    "preferSimulatedAdapters": bool,
    "requireManualReviewOnUnavailable": bool,
    "maxConcurrentVerificationRequests": int,
    "note": str,
}
_UPLOAD_KEYS = {"maxUploadMb": int, "allowedExtensions": list, "autoExtractOnUpload": bool}

# Which settings actually change behaviour, so the screen never implies more control than exists.
SETTING_ENFORCEMENT: dict[str, dict[str, str]] = {
    "uploads": {
        "maxUploadMb": "enforced (can only be lowered below the deployment limit)",
        "allowedExtensions": "enforced (can only narrow the deployment list)",
        "autoExtractOnUpload": "enforced",
    },
    "verification": {
        "enableLiveVerification": "controlled by deployment configuration",
        "preferSimulatedAdapters": "advisory",
        "requireManualReviewOnUnavailable": "advisory — unavailable sources always need manual review",
        "maxConcurrentVerificationRequests": "advisory",
    },
}


def validate_setting_value(key: str, value: dict[str, Any]) -> dict[str, Any]:
    from app.core.config import settings as env

    schema = {"verification": _VERIFICATION_KEYS, "uploads": _UPLOAD_KEYS}.get(key)
    if schema is None:
        return value
    errors: list[str] = []
    for k, v in value.items():
        want = schema.get(k)
        if want is None:
            errors.append(f"Unknown field '{k}'. Allowed: {', '.join(sorted(schema))}.")
            continue
        if want is int and (isinstance(v, bool) or not isinstance(v, int)):
            errors.append(f"{k} must be a whole number.")
        elif want is bool and not isinstance(v, bool):
            errors.append(f"{k} must be true or false.")
        elif want is str and not isinstance(v, str):
            errors.append(f"{k} must be text.")
        elif want is list and (not isinstance(v, list) or not all(isinstance(i, str) for i in v)):
            errors.append(f"{k} must be a list of file extensions.")
    if not errors:
        if key == "uploads":
            if "maxUploadMb" in value and not 1 <= value["maxUploadMb"] <= env.max_upload_mb:
                errors.append(
                    f"maxUploadMb must be between 1 and {env.max_upload_mb} (the deployment limit)."
                )
            if "allowedExtensions" in value:
                chosen = {e.strip().lower().lstrip(".") for e in value["allowedExtensions"] if e.strip()}
                if not chosen:
                    errors.append("allowedExtensions cannot be empty.")
                outside = sorted(chosen - set(env.allowed_extension_set))
                if outside:
                    errors.append(
                        f"These types are not allowed by the deployment: {', '.join(outside)}. "
                        f"Allowed: {', '.join(sorted(env.allowed_extension_set))}."
                    )
        if key == "verification":
            if value.get("enableLiveVerification") and not env.enable_live_verification:
                errors.append(
                    "Live verification can only be switched on in the server configuration "
                    "(ENABLE_LIVE_VERIFICATION) together with authorized credentials."
                )
            n = value.get("maxConcurrentVerificationRequests")
            if n is not None and not 1 <= n <= 50:
                errors.append("maxConcurrentVerificationRequests must be between 1 and 50.")
    if errors:
        raise UnprocessableError(" ".join(errors), code="invalid_setting")
    return value


# ---- audit ------------------------------------------------------------------


def _audit_filtered_query(
    db: Session,
    *,
    action: str | None = None,
    actor: str | None = None,
    actor_role: str | None = None,
    application_id: str | None = None,
    application_number: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    category: str | None = None,
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
):
    from app.models.application import Application

    query = db.query(AuditEvent)
    if action:
        query = query.filter(AuditEvent.action.ilike(f"%{action.strip()}%"))
    if category:
        query = query.filter(AuditEvent.action.ilike(f"{category.strip()}.%"))
    if actor:
        query = query.filter(AuditEvent.actor_name.ilike(f"%{actor.strip()}%"))
    if actor_role:
        query = query.filter(AuditEvent.actor_role == actor_role.strip().lower())
    if application_id:
        query = query.filter(AuditEvent.application_id == application_id)
    if application_number:
        ids = [
            a.id
            for a in db.query(Application.id)
            .filter(Application.application_number.ilike(f"%{application_number.strip()}%"))
            .all()
        ]
        query = query.filter(AuditEvent.application_id.in_(ids or ["__none__"]))
    if entity_type:
        query = query.filter(AuditEvent.entity_type == entity_type)
    if entity_id:
        query = query.filter(AuditEvent.entity_id == entity_id)
    if date_from:
        query = query.filter(AuditEvent.created_at >= date_from)
    if date_to:
        query = query.filter(AuditEvent.created_at <= date_to)
    if q:
        like = f"%{q.strip()}%"
        matching_apps = [
            a.id
            for a in db.query(Application.id)
            .filter(
                or_(
                    Application.application_number.ilike(like),
                    Application.institution_name.ilike(like),
                )
            )
            .all()
        ]
        conds = [
            AuditEvent.detail.ilike(like),
            AuditEvent.action.ilike(like),
            AuditEvent.actor_name.ilike(like),
            AuditEvent.entity_type.ilike(like),
            AuditEvent.entity_id == q.strip(),
            AuditEvent.application_id == q.strip(),
        ]
        if matching_apps:
            conds.append(AuditEvent.application_id.in_(matching_apps))
        query = query.filter(or_(*conds))
    return query


def search_audit(
    db: Session,
    user: User,
    *,
    action: str | None = None,
    actor: str | None = None,
    actor_role: str | None = None,
    application_id: str | None = None,
    application_number: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    category: str | None = None,
    q: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[AuditEvent], int]:
    _require_admin(user)
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    query = _audit_filtered_query(
        db,
        action=action,
        actor=actor,
        actor_role=actor_role,
        application_id=application_id,
        application_number=application_number,
        entity_type=entity_type,
        entity_id=entity_id,
        category=category,
        q=q,
        date_from=date_from,
        date_to=date_to,
    )
    total = query.count()
    items = (
        query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).offset(offset).limit(limit).all()
    )
    return items, total


def audit_export_rows(
    db: Session, user: User, *, limit: int = 5000, **filters: Any
) -> list[AuditEvent]:
    _require_admin(user)
    query = _audit_filtered_query(db, **filters)
    return query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(max(1, min(limit, 20000))).all()


def audit_facets(db: Session, user: User) -> dict[str, Any]:
    """Values the audit filters can offer, with counts, so the screen can use dropdowns."""
    _require_admin(user)
    from sqlalchemy import func

    actions = dict(
        db.query(AuditEvent.action, func.count(AuditEvent.id)).group_by(AuditEvent.action).all()
    )
    categories: dict[str, int] = {}
    for name, n in actions.items():
        cat = name.split(".", 1)[0] if "." in name else "other"
        categories[cat] = categories.get(cat, 0) + n
    roles = dict(
        db.query(AuditEvent.actor_role, func.count(AuditEvent.id)).group_by(AuditEvent.actor_role).all()
    )
    entities = {
        k: n
        for k, n in db.query(AuditEvent.entity_type, func.count(AuditEvent.id))
        .group_by(AuditEvent.entity_type)
        .all()
        if k
    }
    first, last = db.query(func.min(AuditEvent.created_at), func.max(AuditEvent.created_at)).one()
    return {
        "categories": [{"value": k, "count": v} for k, v in sorted(categories.items())],
        "actions": [{"value": k, "count": v} for k, v in sorted(actions.items())],
        "actorRoles": [{"value": k, "count": v} for k, v in sorted(roles.items()) if k],
        "entityTypes": [{"value": k, "count": v} for k, v in sorted(entities.items())],
        "total": sum(actions.values()),
        "firstEventAt": first,
        "lastEventAt": last,
    }


def _action_label(action: str) -> str:
    tail = action.split(".", 1)[-1].replace("_", " ").strip()
    return (tail[:1].upper() + tail[1:]) if tail else action


def _application_numbers(db: Session, events: list[AuditEvent]) -> dict[str, str]:
    from app.models.application import Application

    ids = {e.application_id for e in events if e.application_id}
    if not ids:
        return {}
    return {
        a.id: a.application_number
        for a in db.query(Application.id, Application.application_number).filter(Application.id.in_(ids)).all()
    }


def audit_events_to_dicts(db: Session, events: list[AuditEvent], *, full: bool = False) -> list[dict[str, Any]]:
    numbers = _application_numbers(db, events)
    return [audit_event_to_dict(e, application_number=numbers.get(e.application_id or ""), full=full) for e in events]


def audit_event_detail(db: Session, user: User, event_id: str) -> dict[str, Any]:
    _require_admin(user)
    ev = db.get(AuditEvent, event_id)
    if not ev:
        raise NotFoundError("Audit event not found")
    related_q = db.query(AuditEvent).filter(AuditEvent.id != ev.id)
    conds = []
    if ev.entity_id:
        conds.append(AuditEvent.entity_id == ev.entity_id)
    if ev.application_id:
        conds.append(AuditEvent.application_id == ev.application_id)
    related: list[AuditEvent] = []
    if conds:
        related = related_q.filter(or_(*conds)).order_by(AuditEvent.created_at.desc()).limit(15).all()
    out = audit_events_to_dicts(db, [ev], full=True)[0]
    out["related"] = audit_events_to_dicts(db, related)
    return out


def audit_event_to_dict(
    e: AuditEvent, *, application_number: str | None = None, full: bool = False
) -> dict[str, Any]:
    detail = e.detail or ""
    return {
        "id": e.id,
        "action": e.action,
        "label": _action_label(e.action),
        "category": e.action.split(".", 1)[0] if "." in e.action else "other",
        "actor": e.actor_name,
        "actorId": e.actor_id,
        "actorRole": e.actor_role,
        "timestamp": e.created_at,
        "detail": detail if full else detail[:1000],
        "applicationId": e.application_id,
        "applicationNumber": application_number,
        "entityType": e.entity_type,
        "entityId": e.entity_id,
        "metadata": _scrub_metadata(e.event_metadata if isinstance(e.event_metadata, dict) else {}),
    }


def user_to_dict(u: User) -> dict[str, Any]:
    return {
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "role": u.role.value if hasattr(u.role, "value") else u.role,
        "institutionId": u.institution_id,
        "institutionName": u.institution.name if u.institution else None,
        "isActive": u.is_active,
        "createdAt": getattr(u, "created_at", None),
    }


def category_to_dict(c: ApplicationCategory) -> dict[str, Any]:
    return {
        "id": c.id,
        "code": c.code,
        "name": c.name,
        "description": c.description,
        "requiredDocuments": c.required_documents or [],
        "isActive": c.is_active,
    }


def rule_to_dict(r: RegulatoryRule) -> dict[str, Any]:
    versions = sorted(r.versions or [], key=lambda v: v.created_at or datetime.min)
    return {
        "id": r.id,
        "ruleCode": r.code,
        "name": r.name,
        "description": r.description,
        "handbookRef": r.handbook_ref,
        "verifiedSourceRef": getattr(r, "verified_source_ref", "") or "",
        "isSynthetic": r.is_synthetic,
        "isActive": r.is_active,
        "currentVersion": r.current_version,
        "versions": [
            {
                "id": v.id,
                "version": v.version,
                "definition": v.definition or {},
                "status": getattr(v, "status", None) or "published",
                "changeReason": getattr(v, "change_reason", "") or "",
                "createdById": getattr(v, "created_by_id", None),
                "effectiveFrom": v.effective_from,
                "effectiveTo": getattr(v, "effective_to", None),
                "publishedAt": getattr(v, "published_at", None),
                "createdAt": v.created_at,
            }
            for v in versions
        ],
    }


def setting_to_dict(s: SystemSetting) -> dict[str, Any]:
    return {
        "key": s.key,
        "value": s.value or {},
        "description": s.description,
        "updatedById": s.updated_by_id,
        "changeReason": s.change_reason,
        "updatedAt": s.updated_at,
        "enforcement": SETTING_ENFORCEMENT.get(s.key, {}),
    }
