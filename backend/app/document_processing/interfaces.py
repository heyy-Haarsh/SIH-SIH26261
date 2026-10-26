"""Abstract interfaces for the ten pipeline modules.

Principle: AI assists; deterministic rules evaluate; external sources verify when
available; humans decide. Every module reports its capability truthfully through
``capability()`` so the UI/findings never imply analysis that did not happen.

Modules (numbering follows the PRAMAN pipeline order; the numbering below is the
backend's interpretation of the ten-module pipeline):

 1. Intake             - file validation, checksum, metadata
 2. Classification     - which requirement does this document appear to be?
 3. Extraction         - pull candidate fields out of content (OCR/AI optional)
 4. Normalization      - canonicalise extracted values (dates, whitespace, names)
 5. Reconciliation     - cross-document consistency of extracted fields
 6. Rule evaluation    - deterministic regulatory rules (see app/rules/engine.py)
 7. Verification       - external source checks (see app/integrations)
 8. Forensics          - tamper / authenticity signals
 9. Aggregation        - combine module outputs into structured findings
10. Review support     - assemble a packet for the human officer (no auto decisions)
"""

from abc import ABC, abstractmethod
from typing import Any, Optional

from app.document_processing.types import (
    AggregationResult,
    ClassificationResult,
    DiscrepancyDraft,
    EvalContext,
    ExtractedFieldDraft,
    FieldRecord,
    FindingDraft,
    IntakeResult,
    ModuleResult,
)


class PipelineModule(ABC):
    name: str = "module"

    @abstractmethod
    def capability(self) -> ModuleResult:
        """Report what this module can honestly do in the current deployment."""


# 1
class IntakeModule(PipelineModule):
    @abstractmethod
    def inspect(
        self, *, file_name: Optional[str], declared_content_type: Optional[str], content: bytes
    ) -> IntakeResult: ...


# 2
class ClassificationModule(PipelineModule):
    @abstractmethod
    def classify(self, *, file_name: str, text: Optional[str] = None) -> ClassificationResult: ...


# 3
class ExtractionModule(PipelineModule):
    @abstractmethod
    def extract(
        self, *, file_name: str, extension: str, content: bytes
    ) -> list[ExtractedFieldDraft]: ...


# 4
class NormalizationModule(PipelineModule):
    @abstractmethod
    def normalize(self, fields: list[ExtractedFieldDraft]) -> list[ExtractedFieldDraft]: ...


# 5
class ReconciliationModule(PipelineModule):
    @abstractmethod
    def reconcile(self, records: list[FieldRecord]) -> list[DiscrepancyDraft]: ...


# 6
class RuleEvaluationModule(PipelineModule):
    @abstractmethod
    def evaluate(self, ctx: EvalContext, active_rules: Optional[dict[str, Any]] = None) -> list[FindingDraft]: ...


# 7
class VerificationModule(PipelineModule):
    @abstractmethod
    def verify(self, claims: list[Any]) -> list[Any]: ...


# 8
class ForensicsModule(PipelineModule):
    @abstractmethod
    def analyze(self, *, file_name: str, content: Optional[bytes] = None) -> ModuleResult: ...


# 9
class AggregationModule(PipelineModule):
    @abstractmethod
    def aggregate(
        self, drafts: list[FindingDraft], module_results: list[ModuleResult]
    ) -> AggregationResult: ...


# 10
class ReviewSupportModule(PipelineModule):
    @abstractmethod
    def build_packet(self, result: AggregationResult) -> dict[str, Any]:
        """Return a summary for a human reviewer. Must never contain an approve/reject decision."""
