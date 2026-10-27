"""Layer 1 — config-driven field/format/date/cross-field rules (synthetic unless stated)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any


@dataclass
class Layer1Check:
    check_code: str
    title: str
    detail: str
    outcome: str  # pass|warning|fail|manual_review|unreadable
    severity: str
    evidence: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)


@dataclass
class Layer1Result:
    status: str  # RuleValidationStatus value
    checks: list[Layer1Check]
    limitations: list[str] = field(default_factory=list)


def _parse_number(value: str | None) -> float | None:
    if not value:
        return None
    raw = value.strip().replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _evaluate_arithmetic_check(
    ac: dict[str, Any], fields: dict[str, str], *, prefix: str
) -> list[Layer1Check]:
    check_id = str(ac.get("id") or "ARITHMETIC")
    lhs_fields = ac.get("fields_lhs") or []
    rhs_fields = ac.get("fields_rhs") or []
    lhs_vals = [_parse_number(fields.get(f)) for f in lhs_fields]
    rhs_vals = [_parse_number(fields.get(f)) for f in rhs_fields]
    if any(v is None for v in lhs_vals + rhs_vals):
        return [
            Layer1Check(
                check_code=f"{check_id}_INCOMPLETE",
                title=f"{prefix}Arithmetic check incomplete: {check_id}",
                detail=ac.get("description") or "Missing numeric fields for arithmetic check.",
                outcome="warning",
                severity="warning",
                evidence={"lhs": lhs_fields, "rhs": rhs_fields},
            )
        ]
    lhs = sum(lhs_vals)  # type: ignore[arg-type]
    rhs = sum(rhs_vals)  # type: ignore[arg-type]
    tol = float(ac.get("tolerance_pct") or 0.0)
    denom = max(abs(rhs), 1e-9)
    pct_diff = abs(lhs - rhs) / denom * 100.0
    severity = str(ac.get("severity") or "failed")
    if pct_diff <= tol:
        return [
            Layer1Check(
                check_code=f"{check_id}_PASS",
                title=f"{prefix}Arithmetic OK: {check_id}",
                detail=ac.get("description") or f"LHS≈RHS within {tol}%",
                outcome="pass",
                severity="info",
                evidence={"lhs": lhs, "rhs": rhs, "pct_diff": pct_diff, "aph_clause": ac.get("aph_clause")},
            )
        ]
    outcome = "warning" if severity == "warning" else "fail"
    return [
        Layer1Check(
            check_code=f"{check_id}_FAIL",
            title=f"{prefix}Arithmetic mismatch: {check_id}",
            detail=ac.get("description") or f"LHS={lhs} RHS={rhs} diff={pct_diff:.2f}%",
            outcome=outcome,
            severity=severity if severity in ("failed", "warning") else "failed",
            evidence={"lhs": lhs, "rhs": rhs, "pct_diff": pct_diff, "aph_clause": ac.get("aph_clause")},
        )
    ]


def _evaluate_conditional_check(
    cc: dict[str, Any], fields: dict[str, str], *, prefix: str
) -> list[Layer1Check]:
    check_id = str(cc.get("id") or "CONDITIONAL")
    cond_field = str(cc.get("condition_field") or "")
    op = str(cc.get("condition_op") or "gt")
    raw_threshold = str(cc.get("condition_value") or "")
    if raw_threshold.upper().startswith("TODO"):
        return [
            Layer1Check(
                check_code=f"{check_id}_TODO",
                title=f"{prefix}Conditional check placeholder: {check_id}",
                detail="condition_value is TODO — check skipped pending APH threshold.",
                outcome="warning",
                severity="warning",
                evidence={"aph_clause": cc.get("aph_clause")},
            )
        ]
    left = _parse_number(fields.get(cond_field))
    right = _parse_number(raw_threshold)
    if left is None or right is None:
        return []
    triggered = False
    if op == "gt":
        triggered = left > right
    elif op == "gte":
        triggered = left >= right
    elif op == "lt":
        triggered = left < right
    elif op == "lte":
        triggered = left <= right
    elif op == "eq":
        triggered = left == right
    if not triggered:
        return [
            Layer1Check(
                check_code=f"{check_id}_SKIP",
                title=f"{prefix}Conditional not triggered: {check_id}",
                detail=f"{cond_field}={left} did not meet {op} {right}",
                outcome="pass",
                severity="info",
                evidence={"condition_field": cond_field, "value": left},
            )
        ]
    missing = [
        f for f in (cc.get("then_require") or []) if not (fields.get(f) or "").strip()
    ]
    severity = str(cc.get("severity") or "failed")
    if missing:
        outcome = "warning" if severity == "warning" else "fail"
        return [
            Layer1Check(
                check_code=f"{check_id}_REQUIRE_MISSING",
                title=f"{prefix}Conditional requirement missing: {check_id}",
                detail=f"Condition met but missing: {', '.join(missing)}",
                outcome=outcome,
                severity=severity if severity in ("failed", "warning") else "failed",
                evidence={"missing": missing, "aph_clause": cc.get("aph_clause")},
            )
        ]
    return [
        Layer1Check(
            check_code=f"{check_id}_REQUIRE_OK",
            title=f"{prefix}Conditional requirements present: {check_id}",
            detail="Condition met and required fields present.",
            outcome="pass",
            severity="info",
            evidence={"aph_clause": cc.get("aph_clause")},
        )
    ]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    raw = value.strip()
    if " to " in raw.lower():
        return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


def evaluate_layer1(
    config: dict[str, Any],
    fields: dict[str, str],
    *,
    today: date | None = None,
    unreadable: bool = False,
) -> Layer1Result:
    today = today or date.today()
    checks: list[Layer1Check] = []
    limitations: list[str] = []
    l1 = config.get("layer1") or {}
    synthetic = bool(config.get("is_synthetic_rules", True))
    prefix = "[SYNTHETIC] " if synthetic else ""

    if unreadable:
        checks.append(
            Layer1Check(
                check_code="DOC_UNREADABLE",
                title=f"{prefix}Document unreadable / extraction failed",
                detail="Scan or PDF text could not be read reliably; rule checks skipped.",
                outcome="unreadable",
                severity="manual_review",
                limitations=["OCR/text extraction unavailable or failed"],
            )
        )
        return Layer1Result(status="unreadable", checks=checks, limitations=["unreadable"])

    for item in l1.get("required_fields") or []:
        if isinstance(item, dict):
            fname = str(item.get("field") or "").strip()
            miss_severity = str(item.get("severity") or "failed")
        else:
            fname = str(item).strip()
            miss_severity = "failed"
        if not fname:
            continue
        val = (fields.get(fname) or "").strip()
        if not val:
            outcome = "warning" if miss_severity == "warning" else "fail"
            checks.append(
                Layer1Check(
                    check_code=f"MISSING_{fname.upper()}",
                    title=f"{prefix}Missing required field: {fname}",
                    detail=f"Required field '{fname}' was not extracted or is empty.",
                    outcome=outcome,
                    severity=miss_severity if miss_severity in ("failed", "warning", "info") else "failed",
                    evidence={"field": fname},
                )
            )
        else:
            checks.append(
                Layer1Check(
                    check_code=f"PRESENT_{fname.upper()}",
                    title=f"{prefix}Field present: {fname}",
                    detail=f"Found value for '{fname}'.",
                    outcome="pass",
                    severity="info",
                    evidence={"field": fname, "value_preview": val[:80]},
                )
            )

    for fmt in l1.get("format_checks") or []:
        fname = fmt.get("field")
        if not fname:
            continue
        val = (fields.get(fname) or "").strip()
        optional = bool(fmt.get("optional"))
        if not val:
            if optional:
                continue
            checks.append(
                Layer1Check(
                    check_code=f"FORMAT_MISSING_{fname.upper()}",
                    title=f"{prefix}Format check skipped (empty): {fname}",
                    detail="Field empty for format validation.",
                    outcome="fail",
                    severity="failed",
                    evidence={"field": fname},
                )
            )
            continue
        pattern = fmt.get("pattern") or fmt.get("regex") or ".*"
        if str(pattern).upper().startswith("TODO"):
            continue
        fmt_severity = str(fmt.get("severity") or "failed")
        if not re.match(pattern, val):
            outcome = "warning" if fmt_severity == "warning" else "fail"
            checks.append(
                Layer1Check(
                    check_code=f"FORMAT_{fname.upper()}",
                    title=f"{prefix}Invalid format: {fname}",
                    detail=fmt.get("message") or f"Value does not match expected format for {fname}.",
                    outcome=outcome,
                    severity=fmt_severity if fmt_severity in ("failed", "warning") else "failed",
                    evidence={"field": fname, "value_preview": val[:80], "pattern": pattern},
                )
            )

    date_checks = list(l1.get("date_checks") or [])
    for dr in l1.get("date_rules") or []:
        # Plan-style date_rules → internal date_checks
        converted: dict[str, Any] = {"field": dr.get("field"), "ambiguous_is_manual": True}
        if dr.get("op") == "lte" and dr.get("compare_to") == "today":
            converted["not_future"] = True
        if "not_future" in dr:
            converted["not_future"] = bool(dr["not_future"])
        if "not_expired" in dr:
            converted["not_expired"] = bool(dr["not_expired"])
        if "max_age_days" in dr:
            converted["max_age_days"] = dr["max_age_days"]
        date_checks.append(converted)

    for dc in date_checks:
        fname = dc.get("field")
        if not fname:
            continue
        val = (fields.get(fname) or "").strip()
        optional = bool(dc.get("optional"))
        if not val:
            if optional:
                continue
            continue  # required-field pass already covers missing
        parsed = _parse_date(val)
        if parsed is None:
            outcome = "manual_review" if dc.get("ambiguous_is_manual", True) else "fail"
            checks.append(
                Layer1Check(
                    check_code=f"DATE_AMBIGUOUS_{fname.upper()}",
                    title=f"{prefix}Ambiguous date: {fname}",
                    detail=f"Could not unambiguously parse '{val}' as a date.",
                    outcome=outcome,
                    severity="manual_review",
                    evidence={"field": fname, "raw": val[:80]},
                    limitations=["Ambiguous or unsupported date format"],
                )
            )
            continue
        if dc.get("not_future") and parsed > today:
            checks.append(
                Layer1Check(
                    check_code=f"DATE_FUTURE_{fname.upper()}",
                    title=f"{prefix}Future date: {fname}",
                    detail=f"{fname}={parsed.isoformat()} is in the future.",
                    outcome="fail",
                    severity="failed",
                    evidence={"field": fname, "parsed": parsed.isoformat()},
                )
            )
        if dc.get("not_expired") and parsed < today:
            checks.append(
                Layer1Check(
                    check_code=f"DATE_EXPIRED_{fname.upper()}",
                    title=f"{prefix}Expired: {fname}",
                    detail=f"{fname}={parsed.isoformat()} is before today.",
                    outcome="fail",
                    severity="failed",
                    evidence={"field": fname, "parsed": parsed.isoformat(), "flag": "expired"},
                )
            )
        max_age = dc.get("max_age_days")
        if max_age is not None and parsed < today - timedelta(days=int(max_age)):
            checks.append(
                Layer1Check(
                    check_code=f"DATE_TOO_OLD_{fname.upper()}",
                    title=f"{prefix}Date older than allowed window: {fname}",
                    detail=f"{fname} is older than {max_age} days (synthetic demo window).",
                    outcome="warning",
                    severity="warning",
                    evidence={"field": fname, "parsed": parsed.isoformat(), "max_age_days": max_age},
                )
            )

    for xf in l1.get("cross_field_checks") or []:
        xtype = xf.get("type")
        if xtype == "date_order":
            earlier_f = xf.get("earlier")
            later_f = xf.get("later")
            e_raw = (fields.get(earlier_f) or "").strip()
            l_raw = (fields.get(later_f) or "").strip()
            if not e_raw:
                continue
            if not l_raw and xf.get("optional_later"):
                continue
            e_d, l_d = _parse_date(e_raw), _parse_date(l_raw)
            if e_d and l_d and e_d > l_d:
                checks.append(
                    Layer1Check(
                        check_code=f"DATE_ORDER_{earlier_f}_{later_f}".upper(),
                        title=f"{prefix}Date order invalid",
                        detail=f"{earlier_f} must be on or before {later_f}.",
                        outcome="fail",
                        severity="failed",
                        evidence={"earlier": e_d.isoformat(), "later": l_d.isoformat()},
                    )
                )
        elif xtype == "both_or_neither":
            pair = xf.get("fields") or []
            present = [(f, (fields.get(f) or "").strip()) for f in pair]
            has = [bool(v) for _, v in present]
            if any(has) and not all(has):
                checks.append(
                    Layer1Check(
                        check_code="COORD_PAIR_INCOMPLETE",
                        title=f"{prefix}Incomplete coordinate pair",
                        detail="Latitude and longitude must both be present or both absent.",
                        outcome="fail",
                        severity="failed",
                        evidence={"fields": dict(present)},
                    )
                )

    for ac in l1.get("arithmetic_checks") or []:
        checks.extend(_evaluate_arithmetic_check(ac, fields, prefix=prefix))

    for cc in l1.get("conditional_checks") or []:
        checks.extend(_evaluate_conditional_check(cc, fields, prefix=prefix))

    outcomes = {c.outcome for c in checks}
    if "unreadable" in outcomes:
        status = "unreadable"
    elif "fail" in outcomes:
        status = "fail"
    elif "manual_review" in outcomes:
        status = "manual_review"
    elif "warning" in outcomes:
        status = "warning"
    elif not checks:
        status = "manual_review"
        limitations.append("No Layer 1 checks produced results (empty config or no fields).")
        checks.append(
            Layer1Check(
                check_code="LAYER1_EMPTY",
                title=f"{prefix}No Layer 1 signals",
                detail="Configuration produced no pass/fail checks.",
                outcome="manual_review",
                severity="manual_review",
            )
        )
    else:
        status = "pass"

    if synthetic:
        limitations.append(
            "Layer 1 rules are SYNTHETIC demo rules — not official AICTE regulatory determinations."
        )
    limitations.append("Passing Layer 1 never establishes document authenticity.")
    return Layer1Result(status=status, checks=checks, limitations=limitations)
