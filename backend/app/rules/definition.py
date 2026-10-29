"""Controlled, declarative rule definitions for category document requirements.

A rule definition is DATA, never code. It is a JSON object with a fixed schema, a fixed set of
check types and a fixed set of operators. Nothing here uses eval/exec, regular expressions
supplied by users, or SQL. The same definition drives validation, execution, the human-readable
explanation and the list of required inputs, so the explanation can never contradict the rule.

Schema (version 1)::

    {
      "schema_version": 1,
      "check": {"type": "<check type>", ...parameters...},
      "on_fail": "failed" | "warning" | "manual_review",     # default "warning"
      "message": "optional text shown with a failing result"  # <= 300 chars
    }

Evaluation states (``CheckState``): passed, failed, unable_to_evaluate, pending,
source_unavailable, manual_review. "Unable to evaluate" is a statement about the system, never
about the applicant: it is used when a document could not be read or a needed value was not
extracted, and it must not be reported as non-compliance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Optional

from app.document_processing.text_utils import field_label, parse_date

SCHEMA_VERSION = 1
MAX_MESSAGE = 300

# Check states -------------------------------------------------------------------------------
PASSED = "passed"
FAILED = "failed"
UNABLE = "unable_to_evaluate"
PENDING = "pending"
SOURCE_UNAVAILABLE = "source_unavailable"
MANUAL_REVIEW = "manual_review"
CHECK_STATES = (PASSED, FAILED, UNABLE, PENDING, SOURCE_UNAVAILABLE, MANUAL_REVIEW)

ON_FAIL_VALUES = ("failed", "warning", "manual_review")

_FIELD_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
_CODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,63}$")

OPERATORS = ("eq", "ne", "gt", "gte", "lt", "lte")
_OP_TEXT = {
    "eq": "equal to",
    "ne": "not equal to",
    "gt": "greater than",
    "gte": "greater than or equal to",
    "lt": "less than",
    "lte": "less than or equal to",
}
VALUE_TYPES = ("number", "text", "date")

# Named formats. User-supplied regular expressions are deliberately not supported.
_FORMATS: dict[str, tuple[re.Pattern[str], str]] = {
    "numeric": (re.compile(r"^\d+(\.\d+)?$"), "a number"),
    "alphanumeric": (re.compile(r"^[A-Za-z0-9][A-Za-z0-9 /_\-.]*$"), "letters, digits and common separators"),
    "email": (re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"), "an email address"),
    "phone": (re.compile(r"^(\+?91[\- ]?)?[6-9]\d{9}$"), "a 10-digit Indian mobile number"),
    "financial_year": (re.compile(r"^\d{4}-\d{2}$"), "a financial year such as 2024-25"),
}
FORMAT_NAMES = tuple(_FORMATS) + ("date",)

MAX_LIST = 50


def known_fields() -> list[str]:
    """Field names the built-in extractor can produce. Other names are allowed but will report
    ``unable_to_evaluate`` until an extractor supplies them."""
    from app.document_processing.field_extractor import _KEY_ALIASES

    return sorted(set(_KEY_ALIASES.values()))


@dataclass(frozen=True)
class CheckSpec:
    type: str
    label: str
    params: tuple[str, ...]
    required: tuple[str, ...]
    needs_source: bool = False


CHECK_TYPES: dict[str, CheckSpec] = {
    "field_present": CheckSpec("field_present", "Field is present", ("field",), ("field",)),
    "field_format": CheckSpec("field_format", "Field matches a named format", ("field", "format"), ("field", "format")),
    "field_in": CheckSpec("field_in", "Field is one of listed values", ("field", "values"), ("field", "values")),
    "field_compare": CheckSpec(
        "field_compare",
        "Field compared with a value",
        ("field", "operator", "value", "value_type"),
        ("field", "operator", "value"),
        needs_source=True,
    ),
    "date_not_expired": CheckSpec(
        "date_not_expired", "Date has not passed", ("field", "warn_within_days"), ("field",)
    ),
    "date_not_future": CheckSpec("date_not_future", "Date is not in the future", ("field",), ("field",)),
    "date_age_max_days": CheckSpec(
        "date_age_max_days",
        "Date is not older than a limit",
        ("field", "max_days"),
        ("field", "max_days"),
        needs_source=True,
    ),
    "date_order": CheckSpec("date_order", "One date is not after another", ("earlier", "later"), ("earlier", "later")),
    "field_equals_field": CheckSpec(
        "field_equals_field",
        "Field agrees with a field on another document",
        ("field", "other_requirement_code", "other_field"),
        ("field", "other_requirement_code", "other_field"),
    ),
    "file_extension_in": CheckSpec(
        "file_extension_in", "File type is one of listed types", ("extensions",), ("extensions",)
    ),
    "file_size_max": CheckSpec("file_size_max", "File is not larger than a limit", ("max_mb",), ("max_mb",)),
}


# ------------------------------------------------------------------------------------------
# Validation
# ------------------------------------------------------------------------------------------
@dataclass
class ValidationReport:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Things the administrator asked for that this schema cannot express.
    unsupported: list[str] = field(default_factory=list)
    requires_source: bool = False
    required_inputs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "errors": self.errors,
            "warnings": self.warnings,
            "unsupported": self.unsupported,
            "requiresSource": self.requires_source,
            "requiredInputs": self.required_inputs,
        }


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_field_name(report: ValidationReport, name: Any, label: str) -> Optional[str]:
    if not isinstance(name, str) or not _FIELD_RE.match(name):
        report.errors.append(
            f"'{label}' must be a lowercase field name such as 'valid_until' "
            "(letters, digits and underscores, starting with a letter)."
        )
        return None
    if name not in known_fields():
        report.warnings.append(
            f"'{name}' is not produced by the built-in extractor, so this rule will report "
            "'unable to evaluate' unless a value is available for it."
        )
    return name


def validate_definition(definition: Any, *, source_reference: str = "") -> ValidationReport:
    """Validate a definition against the schema. Never raises; returns every problem found."""
    report = ValidationReport()

    if not isinstance(definition, dict):
        report.errors.append("The definition must be a JSON object.")
        report.valid = False
        return report

    allowed_top = {"schema_version", "check", "on_fail", "message"}
    for key in definition:
        if key not in allowed_top:
            report.errors.append(
                f"Unknown property '{key}'. Allowed properties: {', '.join(sorted(allowed_top))}."
            )

    if definition.get("schema_version") != SCHEMA_VERSION:
        report.errors.append(f"'schema_version' must be {SCHEMA_VERSION}.")

    on_fail = definition.get("on_fail", "warning")
    if on_fail not in ON_FAIL_VALUES:
        report.errors.append(f"'on_fail' must be one of: {', '.join(ON_FAIL_VALUES)}.")

    message = definition.get("message")
    if message is not None and (not isinstance(message, str) or len(message) > MAX_MESSAGE):
        report.errors.append(f"'message' must be text of at most {MAX_MESSAGE} characters.")

    check = definition.get("check")
    if not isinstance(check, dict):
        report.errors.append("'check' is required and must be an object with a 'type'.")
        report.valid = False
        return report

    ctype = check.get("type")
    spec = CHECK_TYPES.get(ctype) if isinstance(ctype, str) else None
    if spec is None:
        report.errors.append(
            f"Unsupported check type '{ctype}'. Supported types: {', '.join(CHECK_TYPES)}."
        )
        report.valid = False
        return report

    for key in check:
        if key != "type" and key not in spec.params:
            report.errors.append(
                f"Unknown parameter '{key}' for check '{ctype}'. Allowed: {', '.join(spec.params)}."
            )
    for key in spec.required:
        if key not in check:
            report.errors.append(f"Check '{ctype}' requires '{key}'.")

    inputs: list[str] = []

    def fld(key: str) -> Optional[str]:
        if key not in check:
            return None
        name = _check_field_name(report, check.get(key), key)
        if name:
            inputs.append(name)
        return name

    if ctype in ("field_present", "field_format", "field_in", "field_compare", "date_not_expired",
                 "date_not_future", "date_age_max_days"):
        fld("field")

    if ctype == "field_format" and "format" in check:
        if check["format"] not in FORMAT_NAMES:
            report.errors.append(f"'format' must be one of: {', '.join(FORMAT_NAMES)}.")

    if ctype == "field_in" and "values" in check:
        values = check["values"]
        if not isinstance(values, list) or not values:
            report.errors.append("'values' must be a non-empty list of text values.")
        elif len(values) > MAX_LIST or not all(isinstance(v, str) and 0 < len(v) <= 120 for v in values):
            report.errors.append(f"'values' must be at most {MAX_LIST} non-empty text values (120 chars each).")

    if ctype == "field_compare":
        op = check.get("operator")
        if "operator" in check and op not in OPERATORS:
            report.errors.append(f"Unsupported operator '{op}'. Supported operators: {', '.join(OPERATORS)}.")
        vtype = check.get("value_type")
        if vtype is not None and vtype not in VALUE_TYPES:
            report.errors.append(f"'value_type' must be one of: {', '.join(VALUE_TYPES)}.")
        if "value" in check:
            value = check["value"]
            if vtype in (None, "number") and _is_number(value):
                pass
            elif vtype == "date" and isinstance(value, str) and parse_date(value):
                pass
            elif vtype == "text" and isinstance(value, str) and value:
                if op not in (None, "eq", "ne"):
                    report.errors.append("Text values can only be compared with 'eq' or 'ne'.")
            elif vtype is None and isinstance(value, str) and value:
                report.errors.append("Add 'value_type' ('text' or 'date') when comparing with a text value.")
            else:
                report.errors.append(
                    f"'value' is not compatible with value_type '{vtype or 'number'}'. "
                    "Use a number, a YYYY-MM-DD date or text to match."
                )

    if ctype == "date_not_expired" and "warn_within_days" in check:
        w = check["warn_within_days"]
        if not (isinstance(w, int) and not isinstance(w, bool) and 1 <= w <= 3650):
            report.errors.append("'warn_within_days' must be a whole number from 1 to 3650.")

    if ctype == "date_age_max_days" and "max_days" in check:
        m = check["max_days"]
        if not (isinstance(m, int) and not isinstance(m, bool) and 1 <= m <= 36500):
            report.errors.append("'max_days' must be a whole number from 1 to 36500.")

    if ctype == "date_order":
        for key in ("earlier", "later"):
            name = fld(key)
        if check.get("earlier") and check.get("earlier") == check.get("later"):
            report.errors.append("'earlier' and 'later' must be different fields.")

    if ctype == "field_equals_field":
        fld("field")
        other = check.get("other_requirement_code")
        if "other_requirement_code" in check and (not isinstance(other, str) or not _CODE_RE.match(other)):
            report.errors.append("'other_requirement_code' must be the code of another document requirement.")
        if "other_field" in check:
            name = _check_field_name(report, check.get("other_field"), "other_field")
            if name:
                inputs.append(f"{other}.{name}" if isinstance(other, str) else name)

    if ctype == "file_extension_in" and "extensions" in check:
        ext = check["extensions"]
        if (
            not isinstance(ext, list)
            or not ext
            or len(ext) > 12
            or not all(isinstance(e, str) and re.match(r"^[a-z0-9]{1,8}$", e.lower().lstrip(".")) for e in ext)
        ):
            report.errors.append("'extensions' must be 1-12 file extensions such as [\"pdf\", \"png\"].")

    if ctype == "file_size_max" and "max_mb" in check:
        m = check["max_mb"]
        if not (_is_number(m) and 0 < m <= 100):
            report.errors.append("'max_mb' must be a number greater than 0 and at most 100.")

    # Threshold checks must be grounded in a configured source. The platform never supplies one.
    threshold = spec.needs_source or (ctype == "date_not_expired" and "warn_within_days" in check)
    report.requires_source = bool(threshold)
    if threshold and not (source_reference or "").strip():
        report.errors.append(
            "This check applies a threshold. Provide a source reference (the document, circular "
            "or policy the threshold comes from) before it can be activated. The platform does "
            "not supply regulatory thresholds."
        )

    if ctype in ("file_extension_in", "file_size_max"):
        inputs.append("file metadata")
    report.required_inputs = sorted(set(inputs))
    report.valid = not report.errors
    return report


def severity_of(definition: dict[str, Any]) -> str:
    sev = definition.get("on_fail", "warning") if isinstance(definition, dict) else "warning"
    return sev if sev in ON_FAIL_VALUES else "warning"


def check_type_of(definition: Any) -> str:
    if isinstance(definition, dict) and isinstance(definition.get("check"), dict):
        t = definition["check"].get("type")
        if isinstance(t, str):
            return t
    return "unstructured"


# ------------------------------------------------------------------------------------------
# Human-readable explanation (derived from the definition only)
# ------------------------------------------------------------------------------------------
def explain(definition: dict[str, Any], *, document_name: str = "this document") -> dict[str, Any]:
    check = definition.get("check") or {}
    ctype = check.get("type")
    f = lambda k: field_label(str(check.get(k, ""))) or "the field"  # noqa: E731
    cond: str
    if ctype == "field_present":
        cond = f"{document_name} must contain a value for “{f('field')}”."
    elif ctype == "field_format":
        cond = f"“{f('field')}” must be {_FORMATS[check['format']][1] if check.get('format') in _FORMATS else 'a valid date'}."
    elif ctype == "field_in":
        cond = f"“{f('field')}” must be one of: {', '.join(map(str, check.get('values', [])))}."
    elif ctype == "field_compare":
        cond = f"“{f('field')}” must be {_OP_TEXT.get(check.get('operator'), '?')} {check.get('value')}."
    elif ctype == "date_not_expired":
        extra = (
            f" A warning is raised when it expires within {check['warn_within_days']} days."
            if check.get("warn_within_days")
            else ""
        )
        cond = f"“{f('field')}” must not be earlier than today.{extra}"
    elif ctype == "date_not_future":
        cond = f"“{f('field')}” must not be a date in the future."
    elif ctype == "date_age_max_days":
        cond = f"“{f('field')}” must not be more than {check.get('max_days')} days before today."
    elif ctype == "date_order":
        cond = f"“{f('earlier')}” must not be after “{f('later')}”."
    elif ctype == "field_equals_field":
        cond = (
            f"“{f('field')}” on {document_name} must agree with “{f('other_field')}” on the "
            f"document uploaded for {check.get('other_requirement_code')}."
        )
    elif ctype == "file_extension_in":
        cond = f"The file must be one of these types: {', '.join(str(e).lower().lstrip('.') for e in check.get('extensions', []))}."
    elif ctype == "file_size_max":
        cond = f"The file must not be larger than {check.get('max_mb')} MB."
    else:
        cond = "No executable check is defined yet."

    sev = severity_of(definition)
    fail_text = {
        "failed": "a failed check is recorded for the scrutiny officer",
        "warning": "a warning is recorded for the scrutiny officer",
        "manual_review": "the document is flagged for manual review by the scrutiny officer",
    }[sev]
    custom = (definition.get("message") or "").strip()
    return {
        "condition": cond,
        "onPass": "The check is recorded as passed. This is not a finding of authenticity or approval.",
        "onFail": f"If the condition is not met, {fail_text}." + (f" Message shown: “{custom}”" if custom else ""),
        "onUnable": (
            "If the document cannot be read or the needed value was not extracted, the check is "
            "recorded as “unable to evaluate”. This is not treated as a failure by the institution."
        ),
        "severity": sev,
        "summary": cond,
    }


# ------------------------------------------------------------------------------------------
# Execution
# ------------------------------------------------------------------------------------------
@dataclass
class RuleInput:
    fields: dict[str, str] = field(default_factory=dict)
    extension: str = ""
    size_bytes: int = 0
    # ready | limited | failed | processing | not_run — how well the document could be read.
    extraction_state: str = "ready"
    other_documents: dict[str, dict[str, str]] = field(default_factory=dict)
    today: date = field(default_factory=date.today)


@dataclass
class CheckResult:
    state: str
    message: str
    inputs: dict[str, Any] = field(default_factory=dict)


def _num(raw: Any) -> Optional[float]:
    try:
        return float(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _compare(op: str, a: Any, b: Any) -> bool:
    return {
        "eq": a == b,
        "ne": a != b,
        "gt": a > b,
        "gte": a >= b,
        "lt": a < b,
        "lte": a <= b,
    }[op]


def _fail(definition: dict[str, Any], default: str, inputs: dict[str, Any]) -> CheckResult:
    sev = severity_of(definition)
    msg = (definition.get("message") or "").strip() or default
    return CheckResult(MANUAL_REVIEW if sev == "manual_review" else FAILED, msg, inputs)


def evaluate(definition: dict[str, Any], data: RuleInput) -> CheckResult:
    """Run one validated definition. Callers must validate first; invalid definitions are never run."""
    report = validate_definition(definition, source_reference="x")  # structure only
    structural = [e for e in report.errors if "source reference" not in e]
    if structural:
        return CheckResult(UNABLE, "The rule definition is not valid and was not run.", {})

    check = definition["check"]
    ctype = check["type"]

    # File-level checks need no extraction.
    if ctype == "file_extension_in":
        allowed = [str(e).lower().lstrip(".") for e in check["extensions"]]
        ext = (data.extension or "").lower().lstrip(".")
        if ext in allowed:
            return CheckResult(PASSED, f"File type .{ext} is accepted.", {"extension": ext})
        return _fail(definition, f"File type .{ext or '?'} is not one of: {', '.join(allowed)}.", {"extension": ext})
    if ctype == "file_size_max":
        limit = float(check["max_mb"]) * 1024 * 1024
        if data.size_bytes <= limit:
            return CheckResult(PASSED, "File size is within the limit.", {"sizeBytes": data.size_bytes})
        return _fail(definition, f"File is larger than {check['max_mb']} MB.", {"sizeBytes": data.size_bytes})

    # Everything below depends on extracted fields.
    if data.extraction_state in ("processing", "not_run"):
        return CheckResult(PENDING, "The document has not finished processing yet.", {})

    def get(name: str) -> Optional[str]:
        v = data.fields.get(name)
        return v.strip() if isinstance(v, str) and v.strip() else None

    unreadable = data.extraction_state in ("failed",)

    if ctype == "field_present":
        name = check["field"]
        if get(name):
            return CheckResult(PASSED, f"“{field_label(name)}” was found.", {name: get(name)})
        if unreadable or data.extraction_state == "limited":
            return CheckResult(
                UNABLE,
                "The document could only be partly read, so this field could not be confirmed.",
                {},
            )
        return _fail(definition, f"“{field_label(name)}” was not found in the readable text.", {})

    def need(*names: str) -> Optional[CheckResult]:
        missing = [n for n in names if not get(n)]
        if missing:
            why = (
                "the document could not be read"
                if unreadable
                else f"“{field_label(missing[0])}” was not extracted"
            )
            return CheckResult(UNABLE, f"This check could not be evaluated because {why}.", {})
        return None

    if ctype == "field_format":
        if (r := need(check["field"])) is not None:
            return r
        name, fmt, value = check["field"], check["format"], get(check["field"])
        ok = parse_date(value) is not None if fmt == "date" else bool(_FORMATS[fmt][0].match(value))
        if ok:
            return CheckResult(PASSED, f"“{field_label(name)}” has the expected format.", {name: value})
        return _fail(definition, f"“{field_label(name)}” does not have the expected format.", {name: value})

    if ctype == "field_in":
        if (r := need(check["field"])) is not None:
            return r
        name, value = check["field"], get(check["field"])
        allowed = [str(v).strip().lower() for v in check["values"]]
        if value.lower() in allowed:
            return CheckResult(PASSED, f"“{field_label(name)}” is an accepted value.", {name: value})
        return _fail(definition, f"“{field_label(name)}” is not one of the accepted values.", {name: value})

    if ctype == "field_compare":
        if (r := need(check["field"])) is not None:
            return r
        name, raw = check["field"], get(check["field"])
        vtype = check.get("value_type") or "number"
        op = check["operator"]
        if vtype == "number":
            a, b = _num(raw), float(check["value"])
            if a is None:
                return CheckResult(UNABLE, f"“{field_label(name)}” is not a number and could not be compared.", {name: raw})
        elif vtype == "date":
            a, b = parse_date(raw), parse_date(check["value"])
            if a is None:
                return CheckResult(UNABLE, f"“{field_label(name)}” is not a recognisable date.", {name: raw})
        else:
            a, b = raw.lower(), str(check["value"]).lower()
        if _compare(op, a, b):
            return CheckResult(PASSED, f"“{field_label(name)}” satisfies the condition.", {name: raw})
        return _fail(definition, f"“{field_label(name)}” does not satisfy the condition.", {name: raw})

    if ctype in ("date_not_expired", "date_not_future", "date_age_max_days"):
        if (r := need(check["field"])) is not None:
            return r
        name, raw = check["field"], get(check["field"])
        d = parse_date(raw)
        if d is None:
            return CheckResult(
                MANUAL_REVIEW, f"“{field_label(name)}” could not be read as a date; an officer should confirm it.", {name: raw}
            )
        label = field_label(name)
        if ctype == "date_not_expired":
            if d < data.today:
                return _fail(definition, f"{label} {d.isoformat()} has passed.", {name: d.isoformat()})
            warn = check.get("warn_within_days")
            if warn and d <= data.today + timedelta(days=int(warn)):
                return _fail(
                    definition,
                    f"{label} {d.isoformat()} is within {warn} days of today.",
                    {name: d.isoformat()},
                )
            return CheckResult(PASSED, f"{label} {d.isoformat()} has not passed.", {name: d.isoformat()})
        if ctype == "date_not_future":
            if d > data.today:
                return _fail(definition, f"{label} {d.isoformat()} is in the future.", {name: d.isoformat()})
            return CheckResult(PASSED, f"{label} is not in the future.", {name: d.isoformat()})
        if d < data.today - timedelta(days=int(check["max_days"])):
            return _fail(definition, f"{label} {d.isoformat()} is older than {check['max_days']} days.", {name: d.isoformat()})
        return CheckResult(PASSED, f"{label} is within {check['max_days']} days.", {name: d.isoformat()})

    if ctype == "date_order":
        if (r := need(check["earlier"], check["later"])) is not None:
            return r
        a, b = parse_date(get(check["earlier"])), parse_date(get(check["later"]))
        if a is None or b is None:
            return CheckResult(MANUAL_REVIEW, "One of the dates could not be read; an officer should confirm them.", {})
        inputs = {check["earlier"]: a.isoformat(), check["later"]: b.isoformat()}
        if a <= b:
            return CheckResult(PASSED, "The dates are in the expected order.", inputs)
        return _fail(definition, "The dates are not in the expected order.", inputs)

    if ctype == "field_equals_field":
        if (r := need(check["field"])) is not None:
            return r
        other = data.other_documents.get(check["other_requirement_code"])
        if other is None:
            return CheckResult(
                PENDING, f"The document for {check['other_requirement_code']} has not been uploaded yet.", {}
            )
        ov = other.get(check["other_field"])
        if not (isinstance(ov, str) and ov.strip()):
            return CheckResult(UNABLE, "The other document does not have a readable value for this field.", {})
        a, b = get(check["field"]), ov.strip()
        inputs = {check["field"]: a, f"{check['other_requirement_code']}.{check['other_field']}": b}
        if " ".join(a.lower().split()) == " ".join(b.lower().split()):
            return CheckResult(PASSED, "The values agree.", inputs)
        # A difference is a prompt for human review, never a conclusion about the applicant.
        return CheckResult(MANUAL_REVIEW, "The values differ; an officer should confirm which is correct.", inputs)

    return CheckResult(UNABLE, "This check type is not executable.", {})


# ------------------------------------------------------------------------------------------
# Plain language -> suggestion (deterministic; NEVER executable by itself)
# ------------------------------------------------------------------------------------------
_PHRASE_FIELDS = {
    "registration number": "registration_number",
    "certificate number": "certificate_number",
    "reference number": "reference_number",
    "issue date": "issue_date",
    "date of issue": "issue_date",
    "expiry date": "expiry_date",
    "valid until": "valid_until",
    "validity date": "valid_until",
    "issuing authority": "issuing_authority",
    "address": "address",
    "survey number": "survey_number",
    "plot number": "plot_number",
    "institution name": "institution_name",
    "signatory name": "signatory_name",
    "execution date": "execution_date",
    "stamp paper reference": "stamp_paper_ref",
    "notary": "notary_details",
    "receipt number": "receipt_number",
    "payment amount": "payment_amount",
    "financial year": "financial_year",
    "engineer name": "engineer_name",
    "auditor name": "auditor_name",
}

_FIELD_FIRST = ("expiry_date", "valid_until")


def suggest_from_text(text: str) -> dict[str, Any]:
    """Offer a *proposal* for a structured rule from a sentence.

    This is a small, fixed pattern matcher, not a language model. It returns a proposed
    definition (or None), the assumptions it made, and the clauses it could not express. The
    administrator must review the proposal, edit it if needed and activate it explicitly; the
    text itself is never executed.
    """
    raw = (text or "").strip()
    low = raw.lower()
    assumptions: list[str] = []
    unsupported: list[str] = []
    definition: Optional[dict[str, Any]] = None

    if not raw:
        return {"definition": None, "assumptions": [], "unsupported": ["Describe the check in a sentence."]}

    clauses = [c.strip() for c in re.split(r"\band\b|[;.]", low) if c.strip()]

    def build(check: dict[str, Any], on_fail: str = "warning") -> dict[str, Any]:
        return {"schema_version": SCHEMA_VERSION, "check": check, "on_fail": on_fail}

    candidates: list[dict[str, Any]] = []
    for clause in clauses:
        found: Optional[dict[str, Any]] = None
        if re.search(r"not (?:be )?(?:expired|past)|has not expired|still valid|valid at the time", clause):
            fld = "valid_until"
            assumptions.append("“Expired” is read as the extracted field “valid_until” being earlier than today.")
            found = {"type": "date_not_expired", "field": fld}
        elif m := re.search(r"issued within (?:the )?(?:last|past) (\d+) (day|month|year)s?", clause):
            n = int(m.group(1)) * {"day": 1, "month": 30, "year": 365}[m.group(2)]
            assumptions.append(
                f"{m.group(1)} {m.group(2)}(s) is converted to {n} days (30-day months, 365-day years)."
            )
            assumptions.append("The limit is taken from your wording; supply the source it comes from before activating.")
            found = {"type": "date_age_max_days", "field": "issue_date", "max_days": n}
        elif m := re.search(r"(?:no|not) (?:larger|bigger|more) than (\d+(?:\.\d+)?) ?mb", clause):
            found = {"type": "file_size_max", "max_mb": float(m.group(1))}
        elif m := re.search(r"\b(pdf|png|jpe?g|docx|txt)\b(?: or (pdf|png|jpe?g|docx|txt))* only", clause):
            exts = sorted(set(re.findall(r"pdf|png|jpe?g|docx|txt", clause)))
            found = {"type": "file_extension_in", "extensions": [e.replace("jpeg", "jpg") for e in exts]}
        elif m := re.search(r"(?:must |should )?(?:contain|include|have|show|state|mention|list)s? (?:a |an |the )?([a-z ]{3,40})", clause):
            phrase = m.group(1).strip()
            match = next((f for p, f in _PHRASE_FIELDS.items() if p in phrase), None)
            if match:
                found = {"type": "field_present", "field": match}
                assumptions.append(f"“{phrase}” is read as the extracted field “{match}”.")
            else:
                unsupported.append(f"“{clause}”: no known extracted field matches “{phrase}”.")
                continue
        if found is None:
            unsupported.append(f"“{clause}” cannot be expressed with the supported check types.")
        else:
            candidates.append(found)

    if candidates:
        definition = build(candidates[0])
        for extra in candidates[1:]:
            unsupported.append(
                f"Only one check per rule is supported; create a separate rule for “{extra['type']}”."
            )
    return {"definition": definition, "assumptions": assumptions, "unsupported": unsupported}
