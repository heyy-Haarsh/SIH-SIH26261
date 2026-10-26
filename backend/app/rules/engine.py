"""Deterministic rule engine with SYNTHETIC demo rules.

IMPORTANT: every rule here is a made-up demo rule used to exercise the platform.
None of them is an official AICTE rule, regulation, or handbook provision, and
handbook references are explicit placeholders. The engine is a pure function of
its input context: same input, same findings. No AI is involved.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Optional

from app.document_processing.extraction import field_label, parse_date
from app.document_processing.interfaces import RuleEvaluationModule
from app.document_processing.types import (
    EvalContext,
    EvalDocument,
    EvidenceDraft,
    FindingDraft,
    ModuleResult,
    ModuleStatus,
)
from app.models.enums import FindingSeverity, ValidationOutcome

ENGINE_VERSION = "synthetic-engine-0.1"
RULESET_VERSION = "v0.1-demo"
SYNTHETIC = "[SYNTHETIC]"

_OUTCOME_FOR_SEVERITY = {
    FindingSeverity.FAILED: ValidationOutcome.FAILED,
    FindingSeverity.WARNING: ValidationOutcome.WARNING,
    FindingSeverity.MANUAL_REVIEW: ValidationOutcome.MANUAL_REVIEW,
    FindingSeverity.INFO: ValidationOutcome.PASS,
}


@dataclass(frozen=True)
class RuleRuntime:
    """Active rule configuration resolved from the database (version + parameters)."""

    version: str
    params: dict[str, Any] = field(default_factory=dict)


class Rule(ABC):
    code: str
    name: str  # includes the [SYNTHETIC] label
    description: str
    handbook_ref: str = "Demo handbook (placeholder - not an official reference)"
    default_params: dict[str, Any] = {}

    @abstractmethod
    def evaluate(self, ctx: EvalContext, rt: RuleRuntime) -> list[FindingDraft]: ...

    # helper ---------------------------------------------------------------
    def _draft(
        self,
        runtime: RuleRuntime,
        *,
        title: str,
        description: str,
        severity: FindingSeverity,
        document_id: Optional[str] = None,
        outcome: Optional[ValidationOutcome] = None,
        evidence: Optional[list[EvidenceDraft]] = None,
    ) -> FindingDraft:
        return FindingDraft(
            title=title,
            description=f"{SYNTHETIC} {description}",
            severity=severity,
            outcome=outcome or _OUTCOME_FOR_SEVERITY[severity],
            rule_code=self.code,
            rule_name=self.name,
            rule_version=runtime.version,
            handbook_ref=self.handbook_ref,
            document_id=document_id,
            evidence=evidence or [],
        )


def _doc_ev(doc: EvalDocument, description: str, page: Optional[str] = None) -> EvidenceDraft:
    return EvidenceDraft(
        description=description,
        document_id=doc.document_id,
        document_name=doc.file_name,
        page_reference=page,
    )


# ---------------------------------------------------------------------------
class MandatoryDocumentRule(Rule):
    code = "SYN-RULE-001"
    name = f"{SYNTHETIC} Mandatory document checklist"
    description = "Every document marked mandatory for the category must be uploaded."
    handbook_ref = "Demo handbook §C.1 (placeholder)"

    def evaluate(self, ctx: EvalContext, rt: RuleRuntime) -> list[FindingDraft]:
        uploaded = {d.requirement_code for d in ctx.documents}
        out = []
        for req in ctx.requirements:
            if req.get("mandatory") and req["code"] not in uploaded:
                out.append(
                    self._draft(
                        rt,
                        title=f"Mandatory document missing: {req['name']}",
                        description=(
                            f"'{req['name']}' ({req['code']}) is marked mandatory for category "
                            f"{ctx.category_code} and has not been uploaded."
                        ),
                        severity=FindingSeverity.FAILED,
                        evidence=[EvidenceDraft(description=f"Requirement {req['code']} marked missing")],
                    )
                )
        return out


class AllowedTypeRule(Rule):
    code = "SYN-RULE-002"
    name = f"{SYNTHETIC} Permitted file type per requirement"
    description = "The uploaded file type must be one of the types permitted for the requirement."
    handbook_ref = "Demo handbook §C.2 (placeholder)"

    def evaluate(self, ctx: EvalContext, rt: RuleRuntime) -> list[FindingDraft]:
        reqs = {r["code"]: r for r in ctx.requirements}
        out = []
        for d in ctx.documents:
            req = reqs.get(d.requirement_code)
            allowed = [a.lower() for a in (req or {}).get("allowed_types", [])]
            if req and allowed and d.extension not in allowed:
                out.append(
                    self._draft(
                        rt,
                        title=f"File type not permitted for {req['name']}",
                        description=(
                            f"'.{d.extension}' is not a permitted type for {req['code']} "
                            f"(permitted: {', '.join(allowed)})."
                        ),
                        severity=FindingSeverity.FAILED,
                        document_id=d.document_id,
                        evidence=[_doc_ev(d, f"Extension .{d.extension}; permitted: {', '.join(allowed)}")],
                    )
                )
        return out


class ValidityWindowRule(Rule):
    code = "SYN-RULE-003"
    name = f"{SYNTHETIC} Document validity window"
    description = (
        "Documents whose file name or extracted validity date indicates expiry fail; "
        "documents expiring soon raise a warning."
    )
    handbook_ref = "Demo handbook §X.Y (placeholder)"
    default_params = {"filename_keywords": ["expired"], "warn_within_days": 60}

    def evaluate(self, ctx: EvalContext, rt: RuleRuntime) -> list[FindingDraft]:
        keywords = [k.lower() for k in rt.params.get("filename_keywords", ["expired"])]
        warn_days = int(rt.params.get("warn_within_days", 60))
        out = []
        for d in ctx.documents:
            lowered = d.file_name.lower()
            hit = next((k for k in keywords if k in lowered), None)
            if hit:
                out.append(
                    self._draft(
                        rt,
                        title=f"Document appears expired: {d.requirement_name}",
                        description=f"The file name contains the indicator '{hit}', treated as an expired document in this demo.",
                        severity=FindingSeverity.FAILED,
                        document_id=d.document_id,
                        evidence=[_doc_ev(d, f"File name '{d.file_name}' contains '{hit}'")],
                    )
                )
            for key in ("valid_until", "expiry_date"):
                raw = d.fields.get(key)
                parsed = parse_date(raw) if raw else None
                if not parsed:
                    continue
                label = field_label(key)
                if parsed < ctx.today:
                    out.append(
                        self._draft(
                            rt,
                            title=f"Document validity date has passed: {d.requirement_name}",
                            description=f"{label} {parsed.isoformat()} is before the evaluation date {ctx.today.isoformat()}.",
                            severity=FindingSeverity.FAILED,
                            document_id=d.document_id,
                            evidence=[_doc_ev(d, f"{label}: {parsed.isoformat()}")],
                        )
                    )
                elif parsed <= ctx.today + timedelta(days=warn_days):
                    out.append(
                        self._draft(
                            rt,
                            title=f"Document expires soon: {d.requirement_name}",
                            description=f"{label} {parsed.isoformat()} is within {warn_days} days of the evaluation date.",
                            severity=FindingSeverity.WARNING,
                            document_id=d.document_id,
                            evidence=[_doc_ev(d, f"{label}: {parsed.isoformat()}")],
                        )
                    )
        return out


class FileAdvisoryRule(Rule):
    code = "SYN-RULE-004"
    name = f"{SYNTHETIC} File integrity advisories"
    description = "Surfaces non-blocking local file advisories (type mismatch, encrypted/truncated PDF)."
    handbook_ref = "Demo handbook §D.1 (placeholder)"

    def evaluate(self, ctx: EvalContext, rt: RuleRuntime) -> list[FindingDraft]:
        out = []
        for d in ctx.documents:
            for w in d.warnings:
                out.append(
                    self._draft(
                        rt,
                        title=f"File advisory: {w.code.replace('_', ' ')}",
                        description=w.message,
                        severity=FindingSeverity.WARNING,
                        document_id=d.document_id,
                        evidence=[_doc_ev(d, w.message)],
                    )
                )
        return out


class DuplicateFileRule(Rule):
    code = "SYN-RULE-005"
    name = f"{SYNTHETIC} Duplicate file across requirements"
    description = "The same file (by SHA-256) should not satisfy multiple distinct requirements."
    handbook_ref = "Demo handbook §D.2 (placeholder)"

    def evaluate(self, ctx: EvalContext, rt: RuleRuntime) -> list[FindingDraft]:
        by_hash: dict[str, list[EvalDocument]] = {}
        for d in ctx.documents:
            by_hash.setdefault(d.sha256, []).append(d)
        out = []
        for sha, docs in by_hash.items():
            if len(docs) < 2:
                continue
            names = ", ".join(d.requirement_code for d in docs)
            for d in docs:
                out.append(
                    self._draft(
                        rt,
                        title=f"Identical file used for multiple requirements: {d.requirement_name}",
                        description=f"Identical content (SHA-256 {sha[:12]}…) was uploaded for: {names}.",
                        severity=FindingSeverity.WARNING,
                        document_id=d.document_id,
                        evidence=[_doc_ev(other, f"{other.requirement_code}: {other.file_name}") for other in docs],
                    )
                )
        return out


class ClassificationConsistencyRule(Rule):
    code = "SYN-RULE-006"
    name = f"{SYNTHETIC} Document / requirement consistency (filename heuristic)"
    description = "Flags files whose name suggests a different requirement than the one uploaded for."
    handbook_ref = "Demo handbook §D.3 (placeholder)"

    def evaluate(self, ctx: EvalContext, rt: RuleRuntime) -> list[FindingDraft]:
        out = []
        for d in ctx.documents:
            c = d.classification
            if c and c.label and c.label != d.requirement_code:
                out.append(
                    self._draft(
                        rt,
                        title=f"Document may not match requirement: {d.requirement_name}",
                        description=(
                            f"The file name suggests {c.label}, but it was uploaded for {d.requirement_code}. "
                            "Filename-based hint only; content was not analysed."
                        ),
                        severity=FindingSeverity.MANUAL_REVIEW,
                        document_id=d.document_id,
                        evidence=[_doc_ev(d, c.rationale)],
                    )
                )
        return out


class CrossDocumentConsistencyRule(Rule):
    code = "SYN-RULE-007"
    name = f"{SYNTHETIC} Cross-document identity consistency"
    description = (
        "Identity/location/date fields extracted from different documents should agree. "
        "Outcomes are MATCH/MISMATCH/MISSING_DATA/POSSIBLE_DUPLICATE/MANUAL_REVIEW — never fraud."
    )
    handbook_ref = "Demo handbook §A.B (placeholder)"

    def evaluate(self, ctx: EvalContext, rt: RuleRuntime) -> list[FindingDraft]:
        from app.models.enums import ReconciliationOutcome

        out = []
        for disc in ctx.discrepancies:
            # MATCH results are persisted by the reconciliation service but do not
            # become validation findings.
            if getattr(disc, "outcome", None) == ReconciliationOutcome.MATCH:
                continue
            label = field_label(disc.field_name) if disc.field_name != "_document_hash" else "Document content"
            title = disc.title or f"{label} differs across documents"
            description = disc.description or (
                f"Extracted values for '{label}' require officer confirmation. Not a fraud determination."
            )
            severity = getattr(disc, "severity", None) or FindingSeverity.MANUAL_REVIEW
            outcome = getattr(disc, "validation_outcome", None) or ValidationOutcome.MANUAL_REVIEW
            out.append(
                self._draft(
                    rt,
                    title=title,
                    description=description,
                    severity=severity,
                    outcome=outcome,
                    evidence=[
                        EvidenceDraft(
                            description=(
                                v.evidence_snippet
                                or f'{v.document_name}: "{v.value}"'
                            ),
                            document_id=v.document_id,
                            document_name=v.document_name,
                            page_reference=v.page,
                            extracted_field_id=getattr(v, "extracted_field_id", None),
                        )
                        for v in disc.values
                    ],
                )
            )
        return out


class CapabilityDisclosureRule(Rule):
    code = "SYN-RULE-008"
    name = f"{SYNTHETIC} Analysis capability disclosure"
    description = "Discloses pipeline modules that were unavailable or limited, so absence of a finding is not read as assurance."
    handbook_ref = "Demo handbook §E.1 (placeholder)"

    def evaluate(self, ctx: EvalContext, rt: RuleRuntime) -> list[FindingDraft]:
        gaps = [m for m in ctx.module_results if m.status in (ModuleStatus.UNAVAILABLE, ModuleStatus.LIMITED)]
        if not gaps:
            return []
        return [
            self._draft(
                rt,
                title="Some analysis capabilities are unavailable or limited",
                description=(
                    "No finding does not imply authenticity or compliance for the areas listed. "
                    + " ".join(f"{m.module}: {m.status.value}." for m in gaps)
                ),
                severity=FindingSeverity.INFO,
                outcome=ValidationOutcome.VERIFICATION_UNAVAILABLE,
                evidence=[EvidenceDraft(description=f"{m.module} ({m.status.value}): {m.message}") for m in gaps],
            )
        ]


BUILTIN_RULES: list[Rule] = [
    MandatoryDocumentRule(),
    AllowedTypeRule(),
    ValidityWindowRule(),
    FileAdvisoryRule(),
    DuplicateFileRule(),
    ClassificationConsistencyRule(),
    CrossDocumentConsistencyRule(),
    CapabilityDisclosureRule(),
]


class RuleEngine(RuleEvaluationModule):
    name = "rule_evaluation"

    def __init__(self, rules: Optional[list[Rule]] = None):
        self.rules = rules if rules is not None else BUILTIN_RULES

    def capability(self) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.AVAILABLE,
            message=f"{len(self.rules)} deterministic SYNTHETIC demo rules ({RULESET_VERSION}).",
        )

    def evaluate(
        self, ctx: EvalContext, active_rules: Optional[dict[str, RuleRuntime]] = None
    ) -> list[FindingDraft]:
        """Evaluate rules. ``active_rules`` maps rule code -> runtime; absent codes are skipped.
        When ``None`` every built-in rule runs with its default parameters.
        """
        findings: list[FindingDraft] = []
        for rule in self.rules:
            if active_rules is None:
                runtime = RuleRuntime(RULESET_VERSION, dict(rule.default_params))
            elif rule.code in active_rules:
                runtime = active_rules[rule.code]
                merged = {**rule.default_params, **runtime.params}
                runtime = RuleRuntime(runtime.version, merged)
            else:
                continue
            findings.extend(rule.evaluate(ctx, runtime))
        return findings
