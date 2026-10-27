"""Rule import (JSON) and natural-language rule drafting.

Nothing here ever activates a rule. Imported and drafted rules are stored as **draft** versions
(new rules are created inactive); an administrator must review and activate them explicitly through
the normal publish step, which re-validates the definition.

Natural-language drafting is deterministic pattern matching — there is no AI call. It only produces
a draft when the statement maps onto something the engine actually implements, and says so when it
does not. It never invents a handbook clause: a citation mentioned in the text is flagged as
unverified and is not copied into the rule's official source fields.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.core.errors import UnprocessableError
from app.models.rule import RegulatoryRule, RuleVersion
from app.models.user import User
from app.services.admin_service import validate_rule_definition
from app.services.audit_service import record_audit

MAX_ITEMS = 100
MAX_TEXT = 2000

_ALIASES = {
    "rulecode": "code",
    "rule_code": "code",
    "handbookref": "handbook_ref",
    "verifiedsourceref": "verified_source_ref",
    "issynthetic": "is_synthetic",
    "changereason": "change_reason",
}
_ALLOWED_KEYS = {
    "code", "name", "description", "handbook_ref", "verified_source_ref", "is_synthetic",
    "definition", "version", "change_reason",
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _norm_item(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in raw.items():
        key = _ALIASES.get(str(k).replace("-", "").lower(), str(k))
        out[key] = v
    return out


def parse_payload(text: str | None, rules: list[Any] | None) -> tuple[list[dict[str, Any]], list[str]]:
    """Return (items, file-level errors). Accepts a JSON array or an object with a ``rules`` array."""
    errors: list[str] = []
    data: Any = rules
    if text is not None and text.strip():
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return [], [f"Not valid JSON: {exc.msg} (line {exc.lineno}, column {exc.colno})."]
    if data is None:
        return [], ["Provide a JSON array of rules, or an object with a \"rules\" array."]
    if isinstance(data, dict):
        if isinstance(data.get("rules"), list):
            data = data["rules"]
        else:
            data = [data]
    if not isinstance(data, list):
        return [], ["The top level must be an array of rules or an object with a \"rules\" array."]
    if not data:
        return [], ["The file contains no rules."]
    if len(data) > MAX_ITEMS:
        return [], [f"At most {MAX_ITEMS} rules can be imported at once (found {len(data)})."]
    items: list[dict[str, Any]] = []
    for idx, raw in enumerate(data, start=1):
        if not isinstance(raw, dict):
            errors.append(f"Item {idx}: each rule must be a JSON object.")
            items.append({"_invalid": True})
            continue
        items.append(_norm_item(raw))
    return items, errors


def _next_version(existing: set[str]) -> str:
    n = 1
    while f"v{n}" in existing:
        n += 1
    return f"v{n}"


def validate_items(db: Session, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate every item without writing anything."""
    existing = {
        r.code: r
        for r in db.query(RegulatoryRule).options(joinedload(RegulatoryRule.versions)).all()
    }
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    for idx, item in enumerate(items, start=1):
        errors: list[str] = []
        warnings: list[str] = []
        if item.get("_invalid"):
            results.append({"index": idx, "code": "", "action": "invalid", "valid": False,
                            "errors": ["Each rule must be a JSON object."], "warnings": [], "version": ""})
            continue
        unknown = sorted(set(item) - _ALLOWED_KEYS)
        if unknown:
            warnings.append(f"Ignored unknown field(s): {', '.join(unknown)}.")
        code = str(item.get("code") or "").strip().upper()
        definition = item.get("definition")
        if definition is None:
            definition = {}
        if not isinstance(definition, dict):
            errors.append("definition must be a JSON object.")
            definition = {}
        rule = existing.get(code)
        if code in seen and code:
            errors.append(f"{code} appears more than once in this file.")
        seen.add(code)
        action = "add_draft_version" if rule else "create_rule_draft"
        version = str(item.get("version") or "").strip()
        if rule:
            used = {v.version for v in rule.versions}
            version = version or _next_version(used)
            if version in used:
                errors.append(f"{code} already has a version named '{version}'.")
            is_synth, handbook, source = rule.is_synthetic, rule.handbook_ref, rule.verified_source_ref
        else:
            version = version or "v1"
            is_synth = bool(item.get("is_synthetic", True))
            handbook = str(item.get("handbook_ref") or "").strip()
            source = str(item.get("verified_source_ref") or "").strip()
            if len(str(item.get("name") or "").strip()) < 3:
                errors.append("name is required (at least 3 characters).")
        reason = str(item.get("change_reason") or "").strip() or "Imported as draft; pending review"
        ok, e2, w2 = validate_rule_definition(
            code=code, is_synthetic=is_synth, handbook_ref=handbook, verified_source_ref=source,
            definition=definition, existing_codes=None,
        )
        errors.extend(e2)
        warnings.extend(w2)
        results.append({
            "index": idx,
            "code": code,
            "name": str(item.get("name") or (rule.name if rule else "")).strip(),
            "action": "invalid" if errors else action,
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "version": version,
            "changeReason": reason,
        })
    return results


def import_items(
    db: Session, actor: User, items: list[dict[str, Any]], *, origin: str = "json_import"
) -> dict[str, Any]:
    results = validate_items(db, items)
    bad = [r for r in results if not r["valid"]]
    if bad:
        raise UnprocessableError(
            "Nothing was imported because some rules are invalid: "
            + "; ".join(f"#{r['index']} {r['code'] or '?'}: {' '.join(r['errors'])}" for r in bad),
            code="rule_import_invalid",
            extra={"results": results},
        )
    created: list[dict[str, Any]] = []
    now = _now()
    for item, res in zip(items, results):
        code = res["code"]
        definition = dict(item.get("definition") or {})
        definition.setdefault("draft_origin", origin)
        rule = (
            db.query(RegulatoryRule)
            .options(joinedload(RegulatoryRule.versions))
            .filter(RegulatoryRule.code == code)
            .first()
        )
        rv = RuleVersion(
            version=res["version"], definition=definition, status="draft",
            change_reason=res["changeReason"], created_by_id=actor.id,
        )
        if rule is None:
            is_synth = bool(item.get("is_synthetic", True))
            name = str(item.get("name") or "").strip()
            if is_synth and "SYNTHETIC" not in name.upper():
                name = f"[SYNTHETIC] {name}"
            rule = RegulatoryRule(
                code=code, name=name,
                description=str(item.get("description") or "").strip(),
                handbook_ref=str(item.get("handbook_ref") or "").strip()
                or ("Demo handbook (placeholder — not official AICTE APH)" if is_synth else ""),
                verified_source_ref=str(item.get("verified_source_ref") or "").strip(),
                is_synthetic=is_synth,
                is_active=False,  # inactive until an administrator activates a reviewed version
                current_version=res["version"],
            )
            rule.versions.append(rv)
            db.add(rule)
        else:
            rule.versions.append(rv)
        db.flush()
        record_audit(
            db, action="admin.rule_draft_created", actor=actor.name, actor_id=actor.id,
            actor_role=actor.role.value,
            detail=f"code={code}; version={res['version']}; origin={origin}; status=draft",
            entity_type="rule_version", entity_id=rv.id,
            metadata={"ruleCode": code, "version": res["version"], "origin": origin,
                      "action": res["action"], "definition": definition},
        )
        created.append({"code": code, "version": res["version"], "action": res["action"],
                        "ruleId": rule.id, "activated": False})
    db.commit()
    _ = now
    return {"created": created, "results": results, "activated": 0,
            "message": f"{len(created)} draft(s) saved. Review and activate each one before it affects any check."}


# ---- natural language ---------------------------------------------------------------

_UNIT_DAYS = {"day": 1, "days": 1, "week": 7, "weeks": 7, "month": 30, "months": 30, "year": 365, "years": 365}
_NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "ten": 10, "twelve": 12}
_DURATION = re.compile(
    r"\b(\d{1,4}|" + "|".join(_NUM_WORDS) + r")\s*(days?|weeks?|months?|years?)\b", re.IGNORECASE
)
_CITATION = re.compile(r"\b(clause|section|para(?:graph)?|chapter|page|pg\.?|p\.)\s*[\w.\-]+", re.IGNORECASE)


def _duration_days(text: str) -> tuple[int | None, str]:
    m = _DURATION.search(text)
    if not m:
        return None, ""
    raw = m.group(1).lower()
    n = int(raw) if raw.isdigit() else _NUM_WORDS[raw]
    return n * _UNIT_DAYS[m.group(2).lower()], m.group(0)


def draft_from_text(db: Session, text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if len(text) < 10:
        raise UnprocessableError("Describe the rule in at least a sentence (10+ characters).")
    if len(text) > MAX_TEXT:
        raise UnprocessableError(f"Keep the description under {MAX_TEXT} characters.")
    lower = text.lower()
    interpretation: list[str] = []
    warnings: list[str] = [
        "This is a draft only. It has not been saved and will not affect any check until you review, "
        "save and activate it."
    ]
    citations = [m.group(0) for m in _CITATION.finditer(text)]
    if citations:
        warnings.append(
            f"The text mentions {', '.join(citations)}. References typed here are not verified and are not "
            "copied into the rule; add verified handbook references under Handbook references."
        )

    target_code = ""
    params: dict[str, Any] = {}
    logic = "unrecognized"
    executable = False
    confidence = "low"

    validity_words = ("valid", "expir", "renew", "validity", "remaining", "lapse")
    days, phrase = _duration_days(text)
    if days is not None and any(w in lower for w in validity_words):
        target_code, logic = "SYN-RULE-003", "filename_contains_expired"
        params["warn_within_days"] = days
        interpretation.append(
            f"Warn when a document's validity ends within {days} day(s) (from \"{phrase}\")."
        )
        quoted = re.findall(r"[\"“']([^\"”']{2,40})[\"”']", text)
        if quoted and ("file" in lower or "name" in lower):
            params["filename_keywords"] = [q.strip().lower() for q in quoted]
            interpretation.append(f"Treat file names containing {', '.join(params['filename_keywords'])} as expired.")
        executable, confidence = True, "high"
    elif re.search(r"\b(mandatory|required|compulsory|must be (uploaded|submitted|provided))\b", lower):
        target_code, logic = "SYN-RULE-001", "missing_mandatory"
        interpretation.append("A document must be uploaded before the application can be scrutinised.")
        warnings.append(
            "Mandatory documents are configured per category (Administrator → Categories). This draft records "
            "the intent but does not add a requirement by itself."
        )
        confidence = "high"
    elif re.search(r"\b(match|consistent|same|identical)\b", lower) and re.search(
        r"\b(across|between|all documents|each document|name|address|survey)\b", lower
    ):
        target_code, logic = "SYN-RULE-007", "cross_identity"
        interpretation.append("Key identity fields should agree across all documents.")
        warnings.append(
            "Cross-document consistency already runs on the identity fields the engine knows about. "
            "This draft records the intent; it cannot add a new field to compare."
        )
        confidence = "high"
    else:
        interpretation.append("The statement could not be mapped to a check the engine implements.")
        warnings.append(
            "The engine cannot execute this statement. You can still save it as documentation, but "
            "activating it will not change any result until a developer implements the logic."
        )

    rule = None
    if target_code:
        rule = (
            db.query(RegulatoryRule)
            .options(joinedload(RegulatoryRule.versions))
            .filter(RegulatoryRule.code == target_code)
            .first()
        )
    definition: dict[str, Any] = {"logic": logic, "synthetic": True, "description": text[:300],
                                  "source_text": text, "draft_origin": "natural_language"}
    if rule is not None:
        current = next((v for v in rule.versions if v.version == rule.current_version), None)
        base = dict((current.definition if current else {}) or {})
        merged_params = {**(base.get("params") or {}), **params}
        definition = {**base, **definition, **({"params": merged_params} if merged_params else {})}
        code = rule.code
        name = rule.name
        version = _next_version({v.version for v in rule.versions})
        mode = "new_version_of_existing_rule"
    else:
        digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8].upper()
        code = f"SYN-NL-{digest}"
        name = "[SYNTHETIC] Drafted rule: " + text[:60].rstrip(" .,;") + ("…" if len(text) > 60 else "")
        version = "v1"
        mode = "new_rule"
        if params:
            definition["params"] = params
    ok, errs, warns = validate_rule_definition(
        code=code, is_synthetic=True, handbook_ref=rule.handbook_ref if rule else "",
        verified_source_ref="", definition=definition, existing_codes=None,
    )
    return {
        "requiresReview": True,
        "executable": executable,
        "confidence": confidence,
        "mode": mode,
        "interpretation": interpretation,
        "warnings": warnings,
        "sourceText": text,
        "draft": {
            "code": code,
            "name": name,
            "description": text[:300],
            "version": version,
            "isSynthetic": True,
            "handbookRef": "",
            "verifiedSourceRef": "",
            "definition": definition,
            "changeReason": "Drafted from natural language; pending administrator review",
            "targetRuleCode": target_code or None,
        },
        "validation": {"valid": ok, "errors": errs, "warnings": warns},
    }
