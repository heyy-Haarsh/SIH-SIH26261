"""Category configuration: information fields, document requirements, rules, publishing, pinning.

Lifecycle
---------
* The *working copy* of a category (information fields, requirements, rule versions) is edited by
  administrators and is never seen by applicants.
* ``publish`` validates the working copy and writes an immutable ``CategoryConfigVersion``
  snapshot. Draft rule versions are never part of a snapshot; only versions that an administrator
  explicitly activated are.
* An application is *pinned* to one published snapshot (``Application.config_version_id``). It is
  pinned when the draft is created, re-pinned while it is still a draft (category change, or at
  submission), and frozen once submitted. Moving a submitted application to a newer configuration
  is not automatic; it would need an explicit, audited action (not implemented here).
* Rule results record the rule version, document version and configuration version they used.

Nothing in this module executes administrator-supplied text. Rule logic is a validated data
structure (see ``app.rules.definition``).
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ForbiddenError, NotFoundError, UnprocessableError
from app.core.seed import DEFAULT_DOCS
from app.models.application import Application
from app.models.base import utcnow
from app.models.category import ApplicationCategory
from app.models.category_config import (
    CategoryConfigVersion,
    DocumentRequirement,
    RequirementRule,
    RequirementRuleVersion,
    RuleCheckResult,
)
from app.models.document import Document
from app.models.enums import UserRole
from app.models.user import User
from app.rules import definition as rd
from app.services.audit_service import record_audit

log = logging.getLogger("praman.category_config")

INFO_FIELD_TYPES = ("text", "textarea", "number", "date", "select", "email", "boolean")
# Application columns that the form always collects itself; configured fields may not reuse them.
RESERVED_KEYS = {"institution_name", "program_name", "academic_year", "category_code", "contact_email"}
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,47}$")
_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{1,63}$")
_EXT_RE = re.compile(r"^[a-z0-9]{1,8}$")
SUBMISSION_ALLOWED_EXT = {"pdf", "png", "jpg", "jpeg", "docx", "txt"}


def _require_admin(actor: User) -> None:
    if actor.role != UserRole.REGIONAL_OFFICER:
        raise ForbiddenError("Only a system administrator can change category configuration.")


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ==========================================================================================
# Information fields
# ==========================================================================================
def normalise_info_fields(raw: Any) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (clean fields, errors). Only the defined field schema is accepted."""
    errors: list[str] = []
    if raw is None:
        return [], errors
    if not isinstance(raw, list):
        return [], ["Information fields must be a list."]
    if len(raw) > 40:
        return [], ["A category can have at most 40 information fields."]
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, item in enumerate(raw, start=1):
        where = f"Field {i}"
        if not isinstance(item, dict):
            errors.append(f"{where}: must be an object.")
            continue
        allowed = {"key", "label", "help_text", "type", "required", "options", "min_length",
                   "max_length", "min", "max"}
        for k in item:
            if k not in allowed:
                errors.append(f"{where}: unknown property '{k}'.")
        key = str(item.get("key") or "").strip()
        label = str(item.get("label") or "").strip()
        ftype = str(item.get("type") or "text").strip()
        if not _KEY_RE.match(key):
            errors.append(f"{where}: key must be lowercase letters, digits or underscores (2-48 chars, starting with a letter).")
            continue
        where = f"Field '{key}'"
        if key in RESERVED_KEYS:
            errors.append(f"{where}: this key is reserved by the application form.")
        if key in seen:
            errors.append(f"{where}: duplicate key.")
        seen.add(key)
        if not label or len(label) > 120:
            errors.append(f"{where}: a label of 1-120 characters is required.")
        if ftype not in INFO_FIELD_TYPES:
            errors.append(f"{where}: type must be one of {', '.join(INFO_FIELD_TYPES)}.")
            continue
        field: dict[str, Any] = {
            "key": key,
            "label": label,
            "help_text": str(item.get("help_text") or "").strip()[:300],
            "type": ftype,
            "required": bool(item.get("required", False)),
        }
        if ftype == "select":
            opts = item.get("options")
            if (
                not isinstance(opts, list)
                or not (1 <= len(opts) <= 30)
                or not all(isinstance(o, str) and 0 < len(o.strip()) <= 80 for o in opts)
            ):
                errors.append(f"{where}: a select field needs 1-30 text options.")
                opts = []
            field["options"] = [o.strip() for o in opts]
        for bound, kinds in (("min_length", ("text", "textarea")), ("max_length", ("text", "textarea"))):
            if item.get(bound) is not None:
                v = item[bound]
                if ftype not in kinds or not (isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 5000):
                    errors.append(f"{where}: '{bound}' applies to text fields and must be a whole number up to 5000.")
                else:
                    field[bound] = v
        for bound in ("min", "max"):
            if item.get(bound) is not None:
                v = item[bound]
                if ftype != "number" or isinstance(v, bool) or not isinstance(v, (int, float)):
                    errors.append(f"{where}: '{bound}' applies to number fields and must be a number.")
                else:
                    field[bound] = v
        if field.get("min_length") is not None and field.get("max_length") is not None and field["min_length"] > field["max_length"]:
            errors.append(f"{where}: min_length is larger than max_length.")
        if field.get("min") is not None and field.get("max") is not None and field["min"] > field["max"]:
            errors.append(f"{where}: min is larger than max.")
        out.append(field)
    return out, errors


def validate_info_values(fields: list[dict[str, Any]], values: dict[str, Any]) -> dict[str, str]:
    """Check an applicant's values against the pinned field definitions. Returns key -> message."""
    problems: dict[str, str] = {}
    values = values or {}
    for f in fields:
        key, label = f["key"], f["label"]
        raw = values.get(key)
        empty = raw is None or (isinstance(raw, str) and not raw.strip())
        if f["type"] == "boolean":
            if f.get("required") and raw is not True:
                problems[key] = f"Confirm “{label}”."
            continue
        if empty:
            if f.get("required"):
                problems[key] = f"“{label}” is required."
            continue
        text = str(raw).strip()
        t = f["type"]
        if t in ("text", "textarea"):
            if f.get("min_length") is not None and len(text) < f["min_length"]:
                problems[key] = f"“{label}” must be at least {f['min_length']} characters."
            elif f.get("max_length") is not None and len(text) > f["max_length"]:
                problems[key] = f"“{label}” must be at most {f['max_length']} characters."
        elif t == "number":
            try:
                n = float(text)
            except ValueError:
                problems[key] = f"“{label}” must be a number."
                continue
            if f.get("min") is not None and n < f["min"]:
                problems[key] = f"“{label}” must be at least {f['min']}."
            elif f.get("max") is not None and n > f["max"]:
                problems[key] = f"“{label}” must be at most {f['max']}."
        elif t == "date":
            if rd.parse_date(text) is None:
                problems[key] = f"“{label}” must be a date (YYYY-MM-DD)."
        elif t == "email":
            if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", text):
                problems[key] = f"“{label}” must be an email address."
        elif t == "select":
            if text not in (f.get("options") or []):
                problems[key] = f"Choose one of the listed options for “{label}”."
    return problems


# ==========================================================================================
# Requirements: runtime dicts and snapshots
# ==========================================================================================
def _req_runtime(req: DocumentRequirement) -> dict[str, Any]:
    return {
        "id": req.id,
        "code": req.code,
        "document_type_code": req.document_type_code or req.code,
        "name": req.name,
        "description": req.description or "",
        "mandatory": bool(req.mandatory),
        "allowed_types": list(req.allowed_types or []),
        "max_size_mb": req.max_size_mb,
        "expected_fields": list(req.expected_fields or []),
        "display_order": req.display_order,
    }


def _published_version(rule: RequirementRule) -> Optional[RequirementRuleVersion]:
    return next((v for v in rule.versions if v.status == "published"), None)


def _latest_version(rule: RequirementRule) -> Optional[RequirementRuleVersion]:
    return max(rule.versions, key=lambda v: v.version) if rule.versions else None


def _draft_version(rule: RequirementRule) -> Optional[RequirementRuleVersion]:
    return next((v for v in rule.versions if v.status == "draft"), None)


def _active_requirements(db: Session, category_id: str) -> list[DocumentRequirement]:
    return (
        db.query(DocumentRequirement)
        .filter(DocumentRequirement.category_id == category_id, DocumentRequirement.is_active.is_(True))
        .order_by(DocumentRequirement.display_order, DocumentRequirement.created_at)
        .all()
    )


def _all_requirements(db: Session, category_id: str) -> list[DocumentRequirement]:
    return (
        db.query(DocumentRequirement)
        .filter(DocumentRequirement.category_id == category_id)
        .order_by(DocumentRequirement.display_order, DocumentRequirement.created_at)
        .all()
    )


def build_draft_snapshot(db: Session, cat: ApplicationCategory) -> dict[str, Any]:
    """What would be published right now: active requirements plus activated rule versions only."""
    reqs = []
    for req in _active_requirements(db, cat.id):
        rules = []
        for rule in req.rules:
            pv = _published_version(rule)
            if pv is None:
                continue
            rules.append(
                {
                    "rule_id": rule.id,
                    "rule_version_id": pv.id,
                    "rule_version": pv.version,
                    "code": rule.code,
                    "title": pv.title or rule.title,
                    "description": pv.description,
                    "rule_type": rd.check_type_of(pv.definition),
                    "severity": rd.severity_of(pv.definition),
                    "source_reference": pv.source_reference,
                    "definition": pv.definition,
                }
            )
        item = _req_runtime(req)
        item["rules"] = rules
        reqs.append(item)
    return {
        "category": {"code": cat.code, "name": cat.name, "description": cat.description or ""},
        "info_fields": list(cat.info_fields or []),
        "requirements": reqs,
    }


def _canon(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str)


def diff_snapshots(old: Optional[dict], new: dict) -> list[str]:
    """Plain-language list of what publishing would change."""
    if not old:
        return ["First published configuration."]
    out: list[str] = []
    of = {f["key"]: f for f in old.get("info_fields", [])}
    nf = {f["key"]: f for f in new.get("info_fields", [])}
    for k in nf.keys() - of.keys():
        out.append(f"Information field added: {nf[k]['label']}.")
    for k in of.keys() - nf.keys():
        out.append(f"Information field removed: {of[k]['label']}.")
    for k in nf.keys() & of.keys():
        if _canon(nf[k]) != _canon(of[k]):
            out.append(f"Information field changed: {nf[k]['label']}.")
    orq = {r["id"]: r for r in old.get("requirements", [])}
    nrq = {r["id"]: r for r in new.get("requirements", [])}
    for i in nrq.keys() - orq.keys():
        out.append(f"Document requirement added: {nrq[i]['name']}.")
    for i in orq.keys() - nrq.keys():
        out.append(f"Document requirement removed from this configuration: {orq[i]['name']}.")
    for i in nrq.keys() & orq.keys():
        a, b = orq[i], nrq[i]
        meta = lambda r: _canon({k: v for k, v in r.items() if k != "rules"})  # noqa: E731
        if meta(a) != meta(b):
            out.append(f"Document requirement changed: {b['name']}.")
        ar = {r["rule_id"]: r for r in a.get("rules", [])}
        br = {r["rule_id"]: r for r in b.get("rules", [])}
        for rid in br.keys() - ar.keys():
            out.append(f"Rule activated on {b['name']}: {br[rid]['title']} (v{br[rid]['rule_version']}).")
        for rid in ar.keys() - br.keys():
            out.append(f"Rule deactivated on {b['name']}: {ar[rid]['title']}.")
        for rid in br.keys() & ar.keys():
            if br[rid]["rule_version_id"] != ar[rid]["rule_version_id"]:
                out.append(
                    f"Rule updated on {b['name']}: {br[rid]['title']} "
                    f"(v{ar[rid]['rule_version']} → v{br[rid]['rule_version']})."
                )
    if _canon(old.get("category")) != _canon(new.get("category")):
        out.append("Category name or description changed.")
    return out


def latest_published(db: Session, category_id: str) -> Optional[CategoryConfigVersion]:
    return (
        db.query(CategoryConfigVersion)
        .filter(CategoryConfigVersion.category_id == category_id, CategoryConfigVersion.status == "published")
        .order_by(CategoryConfigVersion.version.desc())
        .first()
    )


def pending_changes(db: Session, cat: ApplicationCategory) -> list[str]:
    pub = latest_published(db, cat.id)
    draft = build_draft_snapshot(db, cat)
    if pub is not None and _canon(pub.snapshot) == _canon(draft):
        return []
    return diff_snapshots(pub.snapshot if pub else None, draft)


# ==========================================================================================
# Validation and publishing
# ==========================================================================================
def validate_configuration(db: Session, cat: ApplicationCategory) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    _, info_errors = normalise_info_fields(cat.info_fields or [])
    errors += [f"Information fields: {e}" for e in info_errors]

    reqs = _active_requirements(db, cat.id)
    codes = {r.code for r in reqs}
    if not reqs:
        warnings.append("No document requirements are active; applicants will not be asked for documents.")
    if not (cat.info_fields or []):
        warnings.append("No additional information fields are configured; only the standard details are collected.")

    rule_count = 0
    for req in reqs:
        if not req.allowed_types:
            errors.append(f"{req.name}: choose at least one accepted file type.")
        for t in req.allowed_types or []:
            if not _EXT_RE.match(str(t)):
                errors.append(f"{req.name}: '{t}' is not a valid file extension.")
        active_rules = [r for r in req.rules if _published_version(r)]
        if not active_rules:
            warnings.append(f"{req.name}: no active rules; only the platform's general checks will apply.")
        for rule in active_rules:
            pv = _published_version(rule)
            rule_count += 1
            rep = rd.validate_definition(pv.definition, source_reference=pv.source_reference)
            for e in rep.errors:
                errors.append(f"{req.name} / {pv.title or rule.title}: {e}")
            check = (pv.definition or {}).get("check", {})
            if check.get("type") == "field_equals_field" and check.get("other_requirement_code") not in codes:
                errors.append(
                    f"{req.name} / {rule.title}: refers to requirement "
                    f"'{check.get('other_requirement_code')}', which is not active in this category."
                )
            if check.get("type") == "file_extension_in" and req.allowed_types:
                allowed = {str(e).lower().lstrip(".") for e in check.get("extensions", [])}
                if not allowed & {str(t).lower() for t in req.allowed_types}:
                    errors.append(
                        f"{req.name} / {rule.title}: its accepted file types never overlap the "
                        "requirement's accepted file types, so every upload would fail."
                    )
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "counts": {
            "infoFields": len(cat.info_fields or []),
            "requirements": len(reqs),
            "activeRules": rule_count,
        },
    }


def publish(db: Session, actor: User, category_id: str, *, note: str = "") -> CategoryConfigVersion:
    _require_admin(actor)
    cat = db.get(ApplicationCategory, category_id)
    if cat is None:
        raise NotFoundError("Category not found.")
    report = validate_configuration(db, cat)
    if not report["valid"]:
        raise UnprocessableError(
            "The configuration has errors and cannot be published: " + " ".join(report["errors"][:5]),
            code="config_invalid",
            extra={"errors": report["errors"], "warnings": report["warnings"]},
        )
    changes = pending_changes(db, cat)
    pub = latest_published(db, cat.id)
    if pub is not None and not changes:
        raise ConflictError("There are no unpublished changes to publish.", code="nothing_to_publish")
    snapshot = build_draft_snapshot(db, cat)
    next_version = (pub.version + 1) if pub else 1
    if pub:
        pub.status = "superseded"
    row = CategoryConfigVersion(
        category_id=cat.id,
        version=next_version,
        status="published",
        snapshot=snapshot,
        summary="; ".join(changes)[:2000] + (f" | Note: {note.strip()}" if note.strip() else ""),
        published_by_id=actor.id,
        published_at=_now(),
    )
    db.add(row)
    db.flush()
    record_audit(
        db,
        action="admin.config_published",
        actor=actor.name,
        actor_id=actor.id,
        actor_role=actor.role.value,
        detail=f"{cat.code} configuration v{next_version} published; {len(changes)} change(s)",
        entity_type="category_config",
        entity_id=row.id,
        metadata={"category": cat.code, "version": next_version, "changes": changes[:50]},
    )
    db.commit()
    db.refresh(row)
    return row


# ==========================================================================================
# Baseline for existing data (idempotent)
# ==========================================================================================
def _code_ok(code: str) -> bool:
    return bool(code) and bool(re.match(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$", code))


def sync_requirements_from_json(db: Session, cat: ApplicationCategory, docs: list[dict]) -> None:
    """Upsert requirement rows from the legacy checklist JSON (by code); deactivate the missing."""
    by_code = {r.code: r for r in _all_requirements(db, cat.id)}
    seen: set[str] = set()
    for order, d in enumerate(docs):
        code = str(d.get("code") or "").strip()
        if not _code_ok(code):
            continue
        seen.add(code)
        types = [str(t).lower().lstrip(".") for t in (d.get("allowed_types") or d.get("allowedTypes") or ["pdf"])]
        row = by_code.get(code)
        if row is None:
            db.add(
                DocumentRequirement(
                    category_id=cat.id,
                    code=code,
                    document_type_code=code,
                    name=str(d.get("name") or code).strip(),
                    mandatory=bool(d.get("mandatory", True)),
                    allowed_types=types,
                    display_order=order,
                    is_active=True,
                )
            )
        else:
            row.name = str(d.get("name") or row.name).strip()
            row.mandatory = bool(d.get("mandatory", row.mandatory))
            row.allowed_types = types
            row.display_order = order
            row.is_active = True
    for code, row in by_code.items():
        if code not in seen:
            row.is_active = False
    db.flush()


def ensure_category_baseline(db: Session, cat: ApplicationCategory) -> None:
    """Give a category requirement rows and a first published configuration if it has none."""
    if db.query(DocumentRequirement).filter(DocumentRequirement.category_id == cat.id).count() == 0:
        legacy = cat.required_documents if isinstance(cat.required_documents, list) else []
        if legacy:
            sync_requirements_from_json(db, cat, legacy)
    if latest_published(db, cat.id) is None:
        db.add(
            CategoryConfigVersion(
                category_id=cat.id,
                version=1,
                status="published",
                snapshot=build_draft_snapshot(db, cat),
                summary="Initial configuration created from the category's existing checklist.",
                published_by_id=None,
                published_at=_now(),
            )
        )
        db.flush()


def ensure_baseline(db: Session) -> None:
    """Idempotent upgrade of existing data to the configuration-driven model."""
    for cat in db.query(ApplicationCategory).all():
        ensure_category_baseline(db, cat)
    # Pin applications that predate version pinning to their category's first configuration.
    for app in db.query(Application).filter(Application.config_version_id.is_(None)).all():
        first = (
            db.query(CategoryConfigVersion)
            .filter(CategoryConfigVersion.category_id == app.category_id)
            .order_by(CategoryConfigVersion.version.asc())
            .first()
        )
        if first:
            app.config_version_id = first.id
    # Link documents to the stable requirement id.
    reqs = {(r.category_id, r.code): r.id for r in db.query(DocumentRequirement).all()}
    for doc in (
        db.query(Document, Application.category_id)
        .join(Application, Application.id == Document.application_id)
        .filter(Document.requirement_id.is_(None))
        .all()
    ):
        d, cat_id = doc
        rid = reqs.get((cat_id, d.requirement_code))
        if rid:
            d.requirement_id = rid
    db.commit()


# ==========================================================================================
# Effective configuration for an application
# ==========================================================================================
def _legacy_requirements(app: Application) -> list[dict[str, Any]]:
    raw = app.category.required_documents if app.category is not None else None
    if isinstance(raw, list) and raw:
        return [
            {
                "id": None,
                "code": str(i.get("code") or "").strip(),
                "name": str(i.get("name") or i.get("code") or "").strip(),
                "mandatory": bool(i.get("mandatory", True)),
                "allowed_types": list(i.get("allowed_types") or i.get("allowedTypes") or []),
                "max_size_mb": None,
                "description": "",
                "expected_fields": [],
                "rules": [],
            }
            for i in raw
            if isinstance(i, dict) and str(i.get("code") or "").strip()
        ]
    return [dict(d, id=None, max_size_mb=None, description="", expected_fields=[], rules=[]) for d in DEFAULT_DOCS]


def pinned_snapshot(app: Application) -> Optional[dict[str, Any]]:
    cv = getattr(app, "config_version", None)
    return cv.snapshot if cv is not None else None


def effective_requirements(app: Application) -> list[dict[str, Any]]:
    """Requirements the application is judged by: its pinned snapshot, else the legacy checklist."""
    snap = pinned_snapshot(app)
    if snap is not None:
        return [dict(r) for r in snap.get("requirements", [])]
    return _legacy_requirements(app)


def effective_info_fields(app: Application) -> list[dict[str, Any]]:
    snap = pinned_snapshot(app)
    return list(snap.get("info_fields", [])) if snap else []


def pin_application(db: Session, app: Application, *, reason: str = "") -> bool:
    """Pin to the category's latest published configuration. Returns True if the pin changed."""
    cat = app.category or db.get(ApplicationCategory, app.category_id)
    if cat is None or not cat.is_active:
        raise UnprocessableError(
            "This application purpose is not available right now.", code="category_unavailable"
        )
    pub = latest_published(db, cat.id)
    if pub is None:
        raise UnprocessableError(
            "This application purpose has no published configuration yet, so applications "
            "cannot be created for it.",
            code="category_config_unavailable",
        )
    if app.config_version_id == pub.id:
        return False
    app.config_version_id = pub.id
    app.config_version = pub
    db.flush()
    return True


# ==========================================================================================
# Serialisation
# ==========================================================================================
def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def rule_version_to_dict(v: RequirementRuleVersion, *, document_name: str = "this document") -> dict[str, Any]:
    has_def = bool(v.definition)
    return {
        "id": v.id,
        "version": v.version,
        "status": v.status,
        "authoringMode": v.authoring_mode,
        "naturalLanguage": v.natural_language,
        "title": v.title,
        "description": v.description,
        "sourceReference": v.source_reference,
        "notes": v.notes,
        "definition": v.definition or {},
        "schemaVersion": v.schema_version,
        "validation": v.validation or {},
        "changeSummary": v.change_summary,
        "createdAt": _iso(v.created_at),
        "updatedAt": _iso(v.updated_at),
        "publishedAt": _iso(v.published_at),
        "explanation": rd.explain(v.definition, document_name=document_name) if has_def and isinstance(v.definition, dict) and "check" in v.definition else None,
    }


def rule_status(rule: RequirementRule) -> str:
    if _published_version(rule):
        return "active"
    if _draft_version(rule):
        return "draft"
    return "inactive"


def rule_to_dict(rule: RequirementRule, *, detail: bool = False) -> dict[str, Any]:
    req = rule.requirement
    pv, dv, lv = _published_version(rule), _draft_version(rule), _latest_version(rule)
    shown = pv or dv or lv
    out: dict[str, Any] = {
        "id": rule.id,
        "code": rule.code,
        "title": shown.title if shown and shown.title else rule.title,
        "description": shown.description if shown else rule.description,
        "ruleType": rd.check_type_of(shown.definition) if shown else "unstructured",
        "status": rule_status(rule),
        "sourceReference": shown.source_reference if shown else rule.source_reference,
        "severity": rd.severity_of(shown.definition) if shown and shown.definition else "warning",
        "activeVersion": pv.version if pv else None,
        "draftVersion": dv.version if dv else None,
        "latestVersion": lv.version if lv else None,
        "updatedAt": _iso(max([v.updated_at for v in rule.versions] + [rule.updated_at]) if rule.versions else rule.updated_at),
        "categoryId": rule.category_id,
        "requirementId": rule.requirement_id,
        "requirementCode": req.code if req else None,
        "requirementName": req.name if req else None,
        "category": {"id": req.category_id, "code": None, "name": None} if req else None,
    }
    if detail:
        doc = req.name if req else "this document"
        out["versions"] = [
            rule_version_to_dict(v, document_name=doc) for v in sorted(rule.versions, key=lambda x: -x.version)
        ]
        out["notes"] = rule.notes
        out["createdAt"] = _iso(rule.created_at)
    return out


def requirement_to_dict(db: Session, req: DocumentRequirement) -> dict[str, Any]:
    rules = list(req.rules)
    active = sum(1 for r in rules if _published_version(r))
    drafts = sum(1 for r in rules if _draft_version(r))
    inactive = sum(1 for r in rules if rule_status(r) == "inactive")
    return {
        "id": req.id,
        "code": req.code,
        "documentTypeCode": req.document_type_code or req.code,
        "name": req.name,
        "description": req.description or "",
        "mandatory": bool(req.mandatory),
        "allowedTypes": list(req.allowed_types or []),
        "maxSizeMb": req.max_size_mb,
        "expectedFields": list(req.expected_fields or []),
        "displayOrder": req.display_order,
        "isActive": bool(req.is_active),
        "activeRules": active,
        "draftRules": drafts,
        "inactiveRules": inactive,
        "totalRules": len(rules),
        "status": "active" if req.is_active else "inactive",
        "updatedAt": _iso(req.updated_at),
    }


def _config_state(db: Session, cat: ApplicationCategory) -> tuple[str, Optional[CategoryConfigVersion]]:
    pub = latest_published(db, cat.id)
    if pub is None:
        return "unpublished", None
    return ("published" if not pending_changes(db, cat) else "unpublished_changes"), pub


def category_summary(db: Session, cat: ApplicationCategory) -> dict[str, Any]:
    reqs = _all_requirements(db, cat.id)
    active_reqs = [r for r in reqs if r.is_active]
    rules = [r for q in reqs for r in q.rules]
    state, pub = _config_state(db, cat)
    stamps = [cat.updated_at] + [r.updated_at for r in reqs] + [
        v.updated_at for r in rules for v in r.versions
    ]
    return {
        "id": cat.id,
        "code": cat.code,
        "name": cat.name,
        "description": cat.description or "",
        "isActive": cat.is_active,
        "status": "active" if cat.is_active else "inactive",
        "infoFieldCount": len(cat.info_fields or []),
        "requiredDocuments": sum(1 for r in active_reqs if r.mandatory),
        "optionalDocuments": sum(1 for r in active_reqs if not r.mandatory),
        "activeRules": sum(1 for r in rules if _published_version(r)),
        "draftRules": sum(1 for r in rules if _draft_version(r)),
        "totalRules": len(rules),
        "configState": state,
        "configVersion": pub.version if pub else None,
        "updatedAt": _iso(max(s for s in stamps if s)),
    }


def list_categories(
    db: Session, actor: User, *, q: str = "", status: str = "", state: str = ""
) -> list[dict[str, Any]]:
    _require_admin(actor)
    rows = db.query(ApplicationCategory).order_by(ApplicationCategory.code).all()
    out = []
    needle = (q or "").strip().lower()
    for cat in rows:
        s = category_summary(db, cat)
        if needle and needle not in s["name"].lower() and needle not in s["code"].lower():
            continue
        if status in ("active", "inactive") and s["status"] != status:
            continue
        if state and s["configState"] != state:
            continue
        out.append(s)
    return out


def category_detail(db: Session, actor: User, category_id: str) -> dict[str, Any]:
    _require_admin(actor)
    cat = db.get(ApplicationCategory, category_id)
    if cat is None:
        raise NotFoundError("Category not found.")
    summary = category_summary(db, cat)
    versions = (
        db.query(CategoryConfigVersion)
        .filter(CategoryConfigVersion.category_id == cat.id)
        .order_by(CategoryConfigVersion.version.desc())
        .all()
    )
    names = {}
    for v in versions:
        if v.published_by_id and v.published_by_id not in names:
            u = db.get(User, v.published_by_id)
            names[v.published_by_id] = u.name if u else None
    return {
        **summary,
        "infoFields": list(cat.info_fields or []),
        "requirements": [requirement_to_dict(db, r) for r in _all_requirements(db, cat.id)],
        "validation": validate_configuration(db, cat),
        "pendingChanges": pending_changes(db, cat),
        "versions": [
            {
                "id": v.id,
                "version": v.version,
                "status": v.status,
                "summary": v.summary,
                "publishedAt": _iso(v.published_at),
                "publishedBy": names.get(v.published_by_id) if v.published_by_id else None,
                "requirementCount": len(v.snapshot.get("requirements", [])),
                "ruleCount": sum(len(r.get("rules", [])) for r in v.snapshot.get("requirements", [])),
            }
            for v in versions
        ],
        "supportedFieldTypes": list(INFO_FIELD_TYPES),
    }


# ==========================================================================================
# Category and requirement editing (working copy)
# ==========================================================================================
def _audit(db: Session, actor: User, action: str, detail: str, *, entity_type: str, entity_id: str, meta: dict | None = None):
    record_audit(
        db,
        action=action,
        actor=actor.name,
        actor_id=actor.id,
        actor_role=actor.role.value,
        detail=detail,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata=meta,
    )


def create_category(db: Session, actor: User, *, code: str, name: str, description: str = "") -> ApplicationCategory:
    _require_admin(actor)
    code = (code or "").strip().upper()
    name = (name or "").strip()
    if not _CODE_RE.match(code):
        raise UnprocessableError("Category identifier must be 2-64 characters: A-Z, 0-9, _ or -.")
    if len(name) < 2:
        raise UnprocessableError("Category name is required.")
    if db.query(ApplicationCategory).filter(ApplicationCategory.code == code).first():
        raise ConflictError(f"Category identifier already exists: {code}", code="duplicate_category")
    cat = ApplicationCategory(
        code=code, name=name, description=(description or "").strip(), required_documents=[], is_active=False,
        info_fields=[],
    )
    db.add(cat)
    db.flush()
    _audit(db, actor, "admin.category_created", f"code={code}", entity_type="category", entity_id=cat.id)
    db.commit()
    db.refresh(cat)
    return cat


def update_category_meta(
    db: Session, actor: User, category_id: str, *, name: str | None, description: str | None, is_active: bool | None
) -> ApplicationCategory:
    _require_admin(actor)
    cat = db.get(ApplicationCategory, category_id)
    if cat is None:
        raise NotFoundError("Category not found.")
    changes = []
    if name is not None and name.strip() != cat.name:
        if len(name.strip()) < 2:
            raise UnprocessableError("Category name is required.")
        cat.name = name.strip()
        changes.append("name")
    if description is not None and description.strip() != (cat.description or ""):
        cat.description = description.strip()
        changes.append("description")
    if is_active is not None and bool(is_active) != cat.is_active:
        if is_active and latest_published(db, cat.id) is None:
            raise UnprocessableError(
                "Publish a configuration before making this category available to institutions.",
                code="category_config_unavailable",
            )
        cat.is_active = bool(is_active)
        changes.append(f"active={cat.is_active}")
    if changes:
        _audit(db, actor, "admin.category_updated", ", ".join(changes), entity_type="category", entity_id=cat.id)
    db.commit()
    db.refresh(cat)
    return cat


def set_info_fields(db: Session, actor: User, category_id: str, fields: Any) -> list[dict[str, Any]]:
    _require_admin(actor)
    cat = db.get(ApplicationCategory, category_id)
    if cat is None:
        raise NotFoundError("Category not found.")
    clean, errors = normalise_info_fields(fields)
    if errors:
        raise UnprocessableError(" ".join(errors[:4]), code="invalid_info_fields", extra={"errors": errors})
    cat.info_fields = clean
    _audit(db, actor, "admin.category_fields_updated", f"{len(clean)} field(s)", entity_type="category", entity_id=cat.id)
    db.commit()
    return clean


def requirement_impact(db: Session, req: DocumentRequirement) -> dict[str, int]:
    apps = (
        db.query(func.count(func.distinct(Document.application_id)))
        .filter(Document.requirement_id == req.id)
        .scalar()
        or 0
    )
    docs = db.query(func.count(Document.id)).filter(Document.requirement_id == req.id).scalar() or 0
    pinned = 0
    for v in db.query(CategoryConfigVersion).filter(CategoryConfigVersion.category_id == req.category_id):
        if any(r.get("id") == req.id for r in v.snapshot.get("requirements", [])):
            pinned += db.query(Application).filter(Application.config_version_id == v.id).count()
    return {"documents": int(docs), "applicationsWithDocuments": int(apps), "applicationsPinned": int(pinned)}


def _clean_requirement_input(data: dict[str, Any], *, creating: bool) -> dict[str, Any]:
    out: dict[str, Any] = {}
    errs: list[str] = []
    if "name" in data:
        n = str(data["name"] or "").strip()
        if not (2 <= len(n) <= 255):
            errs.append("Document name must be 2-255 characters.")
        out["name"] = n
    if "description" in data:
        out["description"] = str(data["description"] or "").strip()[:1000]
    if "mandatory" in data:
        out["mandatory"] = bool(data["mandatory"])
    if "allowed_types" in data:
        types = [str(t).lower().lstrip(".").strip() for t in (data["allowed_types"] or [])]
        if not types or not all(_EXT_RE.match(t) for t in types):
            errs.append("Choose at least one valid file type (for example pdf, png).")
        bad = [t for t in types if t not in SUBMISSION_ALLOWED_EXT]
        if bad:
            errs.append(f"File type(s) not accepted by the platform: {', '.join(bad)}.")
        out["allowed_types"] = sorted(set(types))
    if "max_size_mb" in data:
        m = data["max_size_mb"]
        if m is not None and not (isinstance(m, int) and not isinstance(m, bool) and 1 <= m <= 100):
            errs.append("Maximum size must be a whole number of MB from 1 to 100.")
        out["max_size_mb"] = m
    if "expected_fields" in data:
        ef = data["expected_fields"] or []
        if not isinstance(ef, list) or not all(isinstance(x, str) and re.match(r"^[a-z][a-z0-9_]{1,63}$", x) for x in ef):
            errs.append("Expected fields must be lowercase field names such as valid_until.")
        out["expected_fields"] = list(dict.fromkeys(ef))[:30]
    if "document_type_code" in data:
        dt = str(data["document_type_code"] or "").strip()
        if dt and not _code_ok(dt):
            errs.append("Document type code is not valid.")
        out["document_type_code"] = dt
    if errs:
        raise UnprocessableError(" ".join(errs), code="invalid_requirement", extra={"errors": errs})
    return out


def create_requirement(db: Session, actor: User, category_id: str, data: dict[str, Any]) -> DocumentRequirement:
    _require_admin(actor)
    cat = db.get(ApplicationCategory, category_id)
    if cat is None:
        raise NotFoundError("Category not found.")
    code = str(data.get("code") or "").strip().upper()
    if not _CODE_RE.match(code):
        raise UnprocessableError("Requirement identifier must be 2-64 characters: A-Z, 0-9, _ or -.")
    if db.query(DocumentRequirement).filter(
        DocumentRequirement.category_id == cat.id, DocumentRequirement.code == code
    ).first():
        raise ConflictError(f"This category already has a requirement with identifier {code}.", code="duplicate_requirement")
    clean = _clean_requirement_input({"allowed_types": ["pdf"], "mandatory": True, **data}, creating=True)
    if "name" not in clean:
        raise UnprocessableError("Document name is required.")
    order = (db.query(func.max(DocumentRequirement.display_order)).filter(DocumentRequirement.category_id == cat.id).scalar() or 0) + 1
    req = DocumentRequirement(
        category_id=cat.id,
        code=code,
        document_type_code=clean.pop("document_type_code", "") or code,
        display_order=order,
        is_active=True,
        **clean,
    )
    db.add(req)
    db.flush()
    _audit(db, actor, "admin.requirement_created", f"{cat.code}/{code}", entity_type="requirement", entity_id=req.id)
    db.commit()
    db.refresh(req)
    return req


def update_requirement(
    db: Session, actor: User, requirement_id: str, data: dict[str, Any], *, acknowledge_impact: bool = False
) -> tuple[DocumentRequirement, dict[str, int]]:
    _require_admin(actor)
    req = db.get(DocumentRequirement, requirement_id)
    if req is None:
        raise NotFoundError("Requirement not found.")
    if "code" in data and str(data["code"]).strip().upper() != req.code:
        raise UnprocessableError(
            "A requirement's identifier is permanent because applications and results refer to it. "
            "Deactivate it and create a new one instead.",
            code="requirement_code_immutable",
        )
    is_active = data.pop("is_active", None)
    clean = _clean_requirement_input(data, creating=False)
    impact = requirement_impact(db, req)
    risky = (
        (is_active is False and req.is_active)
        or ("mandatory" in clean and clean["mandatory"] != req.mandatory)
        or ("allowed_types" in clean and clean["allowed_types"] != list(req.allowed_types or []))
    )
    if risky and (impact["applicationsWithDocuments"] or impact["applicationsPinned"]) and not acknowledge_impact:
        raise ConflictError(
            "Existing applications refer to this requirement. Their history is preserved and they "
            "keep the configuration they were created under, but new applications will follow your "
            "change once it is published. Confirm to continue.",
            code="impact_not_acknowledged",
            extra={"impact": impact},
        )
    changed = []
    for k, v in clean.items():
        if getattr(req, k) != v:
            setattr(req, k, v)
            changed.append(k)
    if is_active is not None and bool(is_active) != req.is_active:
        req.is_active = bool(is_active)
        changed.append("active" if is_active else "deactivated")
    if changed:
        _audit(db, actor, "admin.requirement_updated", f"{req.code}: {', '.join(changed)}", entity_type="requirement", entity_id=req.id,
               meta={"impact": impact})
    db.commit()
    db.refresh(req)
    return req, impact


def reorder_requirements(db: Session, actor: User, category_id: str, ordered_ids: list[str]) -> None:
    _require_admin(actor)
    reqs = {r.id: r for r in _all_requirements(db, category_id)}
    if set(ordered_ids) - set(reqs):
        raise UnprocessableError("The order contains a requirement from another category.", code="invalid_order")
    for i, rid in enumerate(ordered_ids):
        reqs[rid].display_order = i
    rest = [r for rid, r in reqs.items() if rid not in ordered_ids]
    for j, r in enumerate(rest, start=len(ordered_ids)):
        r.display_order = j
    _audit(db, actor, "admin.requirements_reordered", f"{len(ordered_ids)} requirement(s)", entity_type="category", entity_id=category_id)
    db.commit()


# ==========================================================================================
# Rules
# ==========================================================================================
def _load_requirement_for_rule(db: Session, requirement_id: str) -> DocumentRequirement:
    req = db.get(DocumentRequirement, requirement_id)
    if req is None:
        raise NotFoundError("Document requirement not found.")
    return req


def _get_rule(db: Session, rule_id: str) -> RequirementRule:
    rule = db.get(RequirementRule, rule_id)
    if rule is None:
        raise NotFoundError("Rule not found.")
    return rule


def _apply_validation(v: RequirementRuleVersion) -> dict[str, Any]:
    if v.definition:
        rep = rd.validate_definition(v.definition, source_reference=v.source_reference)
        out = rep.to_dict()
    else:
        out = {
            "valid": False,
            "errors": ["No structured definition yet. A plain-language description cannot run until a structured definition is supplied and approved."],
            "warnings": [],
            "unsupported": [],
            "requiresSource": False,
            "requiredInputs": [],
        }
    out["validatedAt"] = _now().isoformat()
    v.validation = out
    return out


def _parse_definition(definition: Any) -> Any:
    """Accepts a dict, or JSON text (with a precise syntax message on failure)."""
    if isinstance(definition, str):
        text = definition.strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise UnprocessableError(
                f"The JSON could not be parsed: {exc.msg} (line {exc.lineno}, column {exc.colno}).",
                code="invalid_json",
            ) from exc
    return definition if definition is not None else {}


def validate_rule_input(
    *, definition: Any, source_reference: str = "", requirement: Optional[DocumentRequirement] = None
) -> dict[str, Any]:
    """Validation without saving (the 'Validate definition' button). Never raises on bad JSON."""
    try:
        parsed = _parse_definition(definition)
    except UnprocessableError as exc:
        return {"valid": False, "errors": [exc.message], "warnings": [], "unsupported": [], "requiresSource": False,
                "requiredInputs": [], "explanation": None, "definition": None}
    if not parsed:
        return {"valid": False, "errors": ["The definition is empty."], "warnings": [], "unsupported": [],
                "requiresSource": False, "requiredInputs": [], "explanation": None, "definition": parsed}
    rep = rd.validate_definition(parsed, source_reference=source_reference).to_dict()
    if requirement is not None and isinstance(parsed, dict):
        check = parsed.get("check") or {}
        if check.get("type") == "file_extension_in" and requirement.allowed_types:
            allowed = {str(e).lower().lstrip(".") for e in check.get("extensions", [])}
            if allowed and not allowed & {str(t).lower() for t in requirement.allowed_types}:
                rep["errors"].append("These file types never overlap the requirement's accepted file types.")
                rep["valid"] = False
    rep["explanation"] = (
        rd.explain(parsed, document_name=requirement.name if requirement else "this document")
        if rep["valid"] or (isinstance(parsed, dict) and isinstance(parsed.get("check"), dict) and parsed["check"].get("type") in rd.CHECK_TYPES)
        else None
    )
    rep["definition"] = parsed
    return rep


def create_rule(db: Session, actor: User, requirement_id: str, data: dict[str, Any]) -> RequirementRule:
    _require_admin(actor)
    req = _load_requirement_for_rule(db, requirement_id)
    title = str(data.get("title") or "").strip()
    if not (3 <= len(title) <= 255):
        raise UnprocessableError("Rule title must be 3-255 characters.")
    code = "RR-" + uuid.uuid4().hex[:8].upper()
    rule = RequirementRule(
        category_id=req.category_id,
        requirement_id=req.id,
        code=code,
        title=title,
        description=str(data.get("description") or "").strip(),
        source_reference=str(data.get("source_reference") or "").strip(),
        notes=str(data.get("notes") or "").strip(),
        created_by_id=actor.id,
    )
    db.add(rule)
    db.flush()
    _new_version(db, actor, rule, data)
    _audit(db, actor, "admin.rule_created", f"{code} on {req.code}", entity_type="requirement_rule", entity_id=rule.id)
    db.commit()
    db.refresh(rule)
    return rule


def _new_version(db: Session, actor: User, rule: RequirementRule, data: dict[str, Any]) -> RequirementRuleVersion:
    definition = _parse_definition(data.get("definition"))
    mode = "plain" if data.get("authoring_mode") == "plain" else "json"
    draft = _draft_version(rule)
    latest = _latest_version(rule)
    if draft is None:
        draft = RequirementRuleVersion(
            rule_id=rule.id,
            version=(latest.version + 1) if latest else 1,
            status="draft",
            created_by_id=actor.id,
        )
        db.add(draft)
        rule.versions.append(draft)
    draft.authoring_mode = mode
    draft.natural_language = str(data.get("natural_language") or "").strip()[:2000]
    draft.title = str(data.get("title") or rule.title).strip()
    draft.description = str(data.get("description") or "").strip()
    draft.source_reference = str(data.get("source_reference") or "").strip()
    draft.notes = str(data.get("notes") or "").strip()
    draft.definition = definition if isinstance(definition, dict) else {}
    draft.schema_version = rd.SCHEMA_VERSION
    draft.change_summary = str(data.get("change_summary") or "").strip()[:500]
    _apply_validation(draft)
    rule.title = draft.title or rule.title
    rule.description = draft.description
    rule.source_reference = draft.source_reference
    rule.notes = draft.notes
    rule.rule_type = rd.check_type_of(draft.definition)
    db.flush()
    return draft


def save_rule_draft(db: Session, actor: User, rule_id: str, data: dict[str, Any]) -> RequirementRule:
    """Create or update the rule's draft version. An active version is never modified."""
    _require_admin(actor)
    rule = _get_rule(db, rule_id)
    title = str(data.get("title") or rule.title).strip()
    if not (3 <= len(title) <= 255):
        raise UnprocessableError("Rule title must be 3-255 characters.")
    data = {**data, "title": title}
    _new_version(db, actor, rule, data)
    _audit(db, actor, "admin.rule_draft_saved", f"{rule.code}", entity_type="requirement_rule", entity_id=rule.id)
    db.commit()
    db.refresh(rule)
    return rule


def activate_rule_version(
    db: Session, actor: User, rule_id: str, version: int, *, confirm_interpretation: bool = False
) -> RequirementRule:
    _require_admin(actor)
    rule = _get_rule(db, rule_id)
    v = next((x for x in rule.versions if x.version == version), None)
    if v is None:
        raise NotFoundError("Rule version not found.")
    if v.status != "draft":
        raise ConflictError("Only a draft version can be activated.", code="not_a_draft")
    rep = _apply_validation(v)
    if not rep["valid"]:
        raise UnprocessableError(
            "This rule cannot be activated: " + " ".join(rep["errors"][:4]),
            code="rule_invalid",
            extra={"errors": rep["errors"]},
        )
    if v.authoring_mode == "plain" and not confirm_interpretation:
        raise UnprocessableError(
            "This rule was written in plain language. Review the structured interpretation and "
            "confirm it before activating.",
            code="interpretation_not_confirmed",
        )
    # Dry-run safety: the engine must be able to execute it without raising.
    try:
        rd.evaluate(v.definition, rd.RuleInput())
    except Exception as exc:  # noqa: BLE001
        raise UnprocessableError(f"The rule engine could not execute this definition: {exc.__class__.__name__}.", code="rule_not_executable") from exc
    for other in rule.versions:
        if other.status == "published":
            other.status = "retired"
    v.status = "published"
    v.published_by_id = actor.id
    v.published_at = _now()
    rule.rule_type = rd.check_type_of(v.definition)
    _audit(
        db, actor, "admin.rule_activated",
        f"{rule.code} v{v.version} activated (takes effect for new applications at the next configuration publish)",
        entity_type="requirement_rule", entity_id=rule.id, meta={"version": v.version},
    )
    db.commit()
    db.refresh(rule)
    return rule


def deactivate_rule(db: Session, actor: User, rule_id: str) -> RequirementRule:
    _require_admin(actor)
    rule = _get_rule(db, rule_id)
    pv = _published_version(rule)
    if pv is None:
        raise ConflictError("This rule has no active version.", code="not_active")
    pv.status = "retired"
    _audit(db, actor, "admin.rule_deactivated", f"{rule.code} v{pv.version}", entity_type="requirement_rule", entity_id=rule.id)
    db.commit()
    db.refresh(rule)
    return rule


def discard_rule_draft(db: Session, actor: User, rule_id: str) -> None:
    _require_admin(actor)
    rule = _get_rule(db, rule_id)
    dv = _draft_version(rule)
    if dv is None:
        raise ConflictError("There is no draft to discard.", code="no_draft")
    if len(rule.versions) == 1:
        # Nothing was ever activated, so there is no history to preserve: remove the whole rule.
        for v in list(rule.versions):
            db.delete(v)
        db.flush()
        db.delete(rule)
    else:
        db.delete(dv)
    _audit(db, actor, "admin.rule_draft_discarded", rule.code, entity_type="requirement_rule", entity_id=rule_id)
    db.commit()


def edit_active_rule(db: Session, actor: User, rule_id: str) -> RequirementRule:
    """Start an edit of an active rule: copy the active version into a new draft."""
    _require_admin(actor)
    rule = _get_rule(db, rule_id)
    if _draft_version(rule):
        return rule
    src = _published_version(rule) or _latest_version(rule)
    if src is None:
        raise NotFoundError("Rule has no versions.")
    _new_version(
        db, actor, rule,
        {
            "title": src.title or rule.title,
            "description": src.description,
            "source_reference": src.source_reference,
            "notes": src.notes,
            "definition": src.definition,
            "authoring_mode": src.authoring_mode,
            "natural_language": src.natural_language,
            "change_summary": f"Edited from v{src.version}",
        },
    )
    db.commit()
    db.refresh(rule)
    return rule


def duplicate_rule(db: Session, actor: User, rule_id: str) -> RequirementRule:
    _require_admin(actor)
    rule = _get_rule(db, rule_id)
    src = _published_version(rule) or _draft_version(rule) or _latest_version(rule)
    return create_rule(
        db, actor, rule.requirement_id,
        {
            "title": f"{(src.title if src and src.title else rule.title)} (copy)"[:255],
            "description": src.description if src else "",
            "source_reference": src.source_reference if src else "",
            "notes": src.notes if src else "",
            "definition": src.definition if src else {},
            "authoring_mode": src.authoring_mode if src else "json",
            "natural_language": src.natural_language if src else "",
            "change_summary": f"Duplicated from {rule.code}",
        },
    )


def requirement_rules(db: Session, actor: User, requirement_id: str) -> dict[str, Any]:
    _require_admin(actor)
    req = _load_requirement_for_rule(db, requirement_id)
    cat = db.get(ApplicationCategory, req.category_id)
    return {
        "category": {"id": cat.id, "code": cat.code, "name": cat.name},
        "requirement": requirement_to_dict(db, req),
        "rules": [rule_to_dict(r) for r in req.rules],
    }


def rule_detail(db: Session, actor: User, rule_id: str) -> dict[str, Any]:
    _require_admin(actor)
    rule = _get_rule(db, rule_id)
    cat = db.get(ApplicationCategory, rule.category_id)
    out = rule_to_dict(rule, detail=True)
    out["category"] = {"id": cat.id, "code": cat.code, "name": cat.name}
    return out


def dry_run(db: Session, actor: User, requirement_id: str, *, definition: Any, source_reference: str, sample: dict[str, Any]) -> dict[str, Any]:
    _require_admin(actor)
    req = _load_requirement_for_rule(db, requirement_id)
    rep = validate_rule_input(definition=definition, source_reference=source_reference, requirement=req)
    if not rep["valid"]:
        return {"validation": rep, "result": None}
    data = rd.RuleInput(
        fields={str(k): str(v) for k, v in (sample.get("fields") or {}).items()},
        extension=str(sample.get("extension") or ""),
        size_bytes=int(sample.get("size_bytes") or sample.get("sizeBytes") or 0),
        extraction_state=str(sample.get("extraction_state") or sample.get("extractionState") or "ready"),
        other_documents={
            str(c): {str(k): str(v) for k, v in (f or {}).items()}
            for c, f in (sample.get("other_documents") or sample.get("otherDocuments") or {}).items()
        },
    )
    res = rd.evaluate(rep["definition"], data)
    return {"validation": rep, "result": {"state": res.state, "message": res.message, "inputs": res.inputs}}


def rules_overview(
    db: Session,
    actor: User,
    *,
    category_id: str = "",
    requirement_id: str = "",
    status: str = "",
    rule_type: str = "",
    config_version: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Cross-category listing. Each row names its owning category and requirement."""
    _require_admin(actor)
    cats = {c.id: c for c in db.query(ApplicationCategory).all()}
    out: list[dict[str, Any]] = []
    if config_version is not None:
        q = db.query(CategoryConfigVersion).filter(CategoryConfigVersion.version == config_version)
        if category_id:
            q = q.filter(CategoryConfigVersion.category_id == category_id)
        for cv in q.all():
            cat = cats.get(cv.category_id)
            for req in cv.snapshot.get("requirements", []):
                if requirement_id and req.get("id") != requirement_id:
                    continue
                for r in req.get("rules", []):
                    if rule_type and r.get("rule_type") != rule_type:
                        continue
                    out.append(
                        {
                            "id": r["rule_id"], "code": r["code"], "title": r["title"], "description": r.get("description", ""),
                            "ruleType": r.get("rule_type"), "status": "active" if cv.status == "published" else "superseded",
                            "activeVersion": r["rule_version"], "draftVersion": None, "latestVersion": r["rule_version"],
                            "sourceReference": r.get("source_reference", ""), "updatedAt": _iso(cv.published_at),
                            "categoryId": cv.category_id,
                            "category": {"id": cv.category_id, "code": cat.code if cat else None, "name": cat.name if cat else None},
                            "requirementId": req.get("id"), "requirementCode": req.get("code"), "requirementName": req.get("name"),
                            "configVersion": cv.version,
                        }
                    )
        return out
    q = db.query(RequirementRule)
    if category_id:
        q = q.filter(RequirementRule.category_id == category_id)
    if requirement_id:
        q = q.filter(RequirementRule.requirement_id == requirement_id)
    if rule_type:
        q = q.filter(RequirementRule.rule_type == rule_type)
    for rule in q.order_by(RequirementRule.updated_at.desc()).all():
        if status and rule_status(rule) != status:
            continue
        row = rule_to_dict(rule)
        cat = cats.get(rule.category_id)
        row["category"] = {"id": rule.category_id, "code": cat.code if cat else None, "name": cat.name if cat else None}
        pub = latest_published(db, rule.category_id)
        row["configVersion"] = pub.version if pub else None
        out.append(row)
    return out


# ==========================================================================================
# Applicant-facing configuration
# ==========================================================================================
DECLARATIONS = [
    "I confirm that the details and documents in this application are accurate and complete to the best of my knowledge.",
    "I am authorised to submit this application on behalf of the institution.",
]


def _public_requirement(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": r["code"],
        "name": r["name"],
        "description": r.get("description", ""),
        "mandatory": bool(r.get("mandatory", True)),
        "allowedTypes": list(r.get("allowed_types") or []),
        "maxSizeMb": r.get("max_size_mb"),
        "checks": [
            {"title": x["title"], "meaning": rd.explain(x["definition"], document_name=r["name"])["condition"]}
            for x in r.get("rules", [])
        ],
    }


def _public_field(f: dict[str, Any]) -> dict[str, Any]:
    return {
        "key": f["key"],
        "label": f["label"],
        "helpText": f.get("help_text", ""),
        "type": f["type"],
        "required": bool(f.get("required")),
        "options": f.get("options", []),
        "minLength": f.get("min_length"),
        "maxLength": f.get("max_length"),
        "min": f.get("min"),
        "max": f.get("max"),
    }


def applicant_categories(db: Session) -> list[dict[str, Any]]:
    """Categories institutions may start an application for (active and published)."""
    out = []
    for cat in db.query(ApplicationCategory).filter(ApplicationCategory.is_active.is_(True)).order_by(ApplicationCategory.code):
        pub = latest_published(db, cat.id)
        if pub is None:
            continue
        reqs = pub.snapshot.get("requirements", [])
        out.append(
            {
                "code": cat.code,
                "name": cat.name,
                "description": cat.description or "",
                "requiredDocuments": [
                    {"code": r["code"], "name": r["name"], "mandatory": r["mandatory"], "allowed_types": r["allowed_types"]}
                    for r in reqs
                ],
                "configVersion": pub.version,
                "infoFieldCount": len(pub.snapshot.get("info_fields", [])),
                "mandatoryCount": sum(1 for r in reqs if r["mandatory"]),
                "optionalCount": sum(1 for r in reqs if not r["mandatory"]),
                "available": True,
            }
        )
    return out


def applicant_category_config(db: Session, code: str) -> dict[str, Any]:
    cat = db.query(ApplicationCategory).filter(ApplicationCategory.code == code).first()
    if cat is None or not cat.is_active:
        raise NotFoundError("This application purpose is not available.", code="category_unavailable")
    pub = latest_published(db, cat.id)
    if pub is None:
        raise UnprocessableError(
            "This application purpose has no published configuration.", code="category_config_unavailable"
        )
    snap = pub.snapshot
    return {
        "code": cat.code,
        "name": cat.name,
        "description": cat.description or "",
        "configVersion": pub.version,
        "infoFields": [_public_field(f) for f in snap.get("info_fields", [])],
        "requirements": [_public_requirement(r) for r in snap.get("requirements", [])],
        "declarations": list(DECLARATIONS),
        "limitations": [
            "Uploading a document or passing an automated check does not confirm that it is genuine or that the application meets AICTE requirements. A scrutiny officer reviews every application.",
        ],
    }


def application_config_view(app: Application) -> dict[str, Any]:
    """The pinned configuration as the applicant sees it, with their saved values."""
    snap = pinned_snapshot(app)
    values = dict(app.info_values or {})
    fields = []
    for f in (snap or {}).get("info_fields", []):
        item = _public_field(f)
        item["value"] = values.get(f["key"])
        fields.append(item)
    return {
        "configVersion": app.config_version.version if getattr(app, "config_version", None) else None,
        "configAvailable": snap is not None,
        "infoFields": fields,
    }


def check_state_label(state: str) -> str:
    return {
        "passed": "No issue found by this automated check",
        "failed": "Flagged for the scrutiny officer",
        "manual_review": "Flagged for the scrutiny officer",
        "unable_to_evaluate": "Could not be evaluated automatically",
        "pending": "Waiting for processing",
        "source_unavailable": "An external source was unavailable",
    }.get(state, state)


def results_for_application(db: Session, application_id: str, *, current_only: bool = True) -> list[RuleCheckResult]:
    q = db.query(RuleCheckResult).filter(RuleCheckResult.application_id == application_id)
    if current_only:
        q = q.filter(RuleCheckResult.is_current.is_(True))
    return q.order_by(RuleCheckResult.created_at).all()
