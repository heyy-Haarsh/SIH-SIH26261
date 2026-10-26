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

    for fname in l1.get("required_fields") or []:
        val = (fields.get(fname) or "").strip()
        if not val:
            checks.append(
                Layer1Check(
                    check_code=f"MISSING_{fname.upper()}",
                    title=f"{prefix}Missing required field: {fname}",
                    detail=f"Required field '{fname}' was not extracted or is empty.",
                    outcome="fail",
                    severity="failed",
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
        pattern = fmt.get("pattern") or ".*"
        if not re.match(pattern, val):
            checks.append(
                Layer1Check(
                    check_code=f"FORMAT_{fname.upper()}",
                    title=f"{prefix}Invalid format: {fname}",
                    detail=fmt.get("message") or f"Value does not match expected format for {fname}.",
                    outcome="fail",
                    severity="failed",
                    evidence={"field": fname, "value_preview": val[:80], "pattern": pattern},
                )
            )

    for dc in l1.get("date_checks") or []:
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
