"""Modules 9 & 10: finding aggregation and human review support."""

from typing import Any

from app.document_processing.interfaces import AggregationModule, ReviewSupportModule
from app.document_processing.types import (
    AggregationResult,
    FindingDraft,
    ModuleResult,
    ModuleStatus,
)
from app.models.enums import FindingSeverity, ValidationOutcome

_SEVERITY_ORDER = {
    FindingSeverity.FAILED: 0,
    FindingSeverity.MANUAL_REVIEW: 1,
    FindingSeverity.WARNING: 2,
    FindingSeverity.INFO: 3,
}

OUTCOME_RANK = {
    ValidationOutcome.FAILED: 3,
    ValidationOutcome.MANUAL_REVIEW: 2,
    ValidationOutcome.WARNING: 1,
}


def worst_outcome(outcomes: list[ValidationOutcome]) -> ValidationOutcome:
    """Worst of failed > manual_review > warning > pass (informational outcomes are ignored)."""
    best = ValidationOutcome.PASS
    for o in outcomes:
        if OUTCOME_RANK.get(o, 0) > OUTCOME_RANK.get(best, 0):
            best = o
    return best


class FindingAggregator(AggregationModule):
    name = "aggregation"

    def capability(self) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.AVAILABLE,
            message="Deduplicates and orders findings; computes run summary.",
        )

    def aggregate(
        self, drafts: list[FindingDraft], module_results: list[ModuleResult]
    ) -> AggregationResult:
        unique: dict[tuple, FindingDraft] = {}
        for d in drafts:
            unique.setdefault((d.rule_code, d.document_id, d.title), d)
        findings = sorted(
            unique.values(),
            key=lambda d: (_SEVERITY_ORDER[d.severity], d.rule_code, d.title),
        )

        counts = {s.value: 0 for s in FindingSeverity}
        for f in findings:
            counts[f.severity.value] += 1

        overall = worst_outcome([f.outcome for f in findings])
        summary: dict[str, Any] = {
            "total": len(findings),
            "bySeverity": counts,
            "overallOutcome": overall.value,
            "modules": [
                {"module": m.module, "status": m.status.value, "message": m.message}
                for m in module_results
            ],
            "disclaimer": (
                "Findings are produced by SYNTHETIC demo rules and local file checks. They are not "
                "official AICTE determinations. A human officer decides."
            ),
        }
        return AggregationResult(findings=findings, summary=summary, overall_outcome=overall)


class ReviewSupportPacketBuilder(ReviewSupportModule):
    name = "review_support"

    def capability(self) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.AVAILABLE,
            message="Builds a reviewer summary; never records a decision.",
        )

    def build_packet(self, result: AggregationResult) -> dict[str, Any]:
        return {
            "overallOutcome": result.overall_outcome.value,
            "requiresManualReview": any(
                f.severity == FindingSeverity.MANUAL_REVIEW for f in result.findings
            ),
            "attention": [
                {"title": f.title, "severity": f.severity.value, "rule": f.rule_code}
                for f in result.findings
                if f.severity in (FindingSeverity.FAILED, FindingSeverity.MANUAL_REVIEW)
            ],
            "decisionRequiredFromHuman": True,
        }
