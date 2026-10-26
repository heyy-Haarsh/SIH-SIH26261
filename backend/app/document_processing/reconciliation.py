"""Module 5: cross-document reconciliation of extracted fields.

Outcomes are explainable only: MATCH, MISMATCH, MISSING_DATA, POSSIBLE_DUPLICATE,
MANUAL_REVIEW. Never labels anything as fraud.
"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from app.document_processing.interfaces import ReconciliationModule
from app.document_processing.types import (
    DiscrepancyDraft,
    DiscrepancyValue,
    FieldRecord,
    ModuleResult,
    ModuleStatus,
)
from app.models.enums import FindingSeverity, ReconciliationOutcome, ValidationOutcome

# Fields compared across documents of one application.
RECONCILE_FIELDS = frozenset(
    {
        "institution_name",
        "registration_number",
        "reference_number",
        "certificate_number",
        "trust_name",
        "address",
        "registered_address",
        "issue_date",
        "valid_until",
        "expiry_date",
        "survey_number",
        "plot_number",
        "land_area",
    }
)

DATE_RECONCILE_FIELDS = frozenset({"issue_date", "valid_until", "expiry_date"})
ID_RECONCILE_FIELDS = frozenset(
    {"registration_number", "reference_number", "certificate_number", "survey_number", "plot_number"}
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WS = re.compile(r"\s+")

ENGINE_VERSION = "reconciliation-0.1"

# Human labels for UI / findings
FIELD_LABELS: dict[str, str] = {
    "institution_name": "Institution name",
    "registration_number": "Registration number",
    "reference_number": "Reference number",
    "certificate_number": "Certificate number",
    "trust_name": "Trust / society name",
    "address": "Address",
    "registered_address": "Registered address",
    "issue_date": "Issue date",
    "valid_until": "Valid until",
    "expiry_date": "Expiry date",
    "survey_number": "Survey number",
    "plot_number": "Plot number",
    "land_area": "Land area",
    "_document_hash": "Document content",
}


def field_label(name: str) -> str:
    return FIELD_LABELS.get(name, name.replace("_", " ").title())


def comparable(value: str) -> str:
    """Case/punctuation-insensitive token string for identity fields."""
    return _NON_ALNUM.sub(" ", (value or "").casefold()).strip()


def normalize_for_field(field_name: str, value: str) -> str:
    """Field-aware normalization used for MATCH vs MISMATCH decisions."""
    raw = (value or "").strip()
    if not raw:
        return ""
    if field_name in DATE_RECONCILE_FIELDS:
        from app.document_processing.field_extractor import parse_date

        iso = parse_date(raw)
        return iso or comparable(raw)
    if field_name in ID_RECONCILE_FIELDS:
        # Keep leading zeros; strip spaces/hyphens/punctuation only
        return _NON_ALNUM.sub("", raw.casefold())
    if field_name == "land_area":
        # Collapse "2.5 acres" / "2.5 Acres" / "2,5 acres"
        cleaned = raw.casefold().replace(",", ".")
        return _WS.sub(" ", cleaned).strip()
    if field_name in {"address", "registered_address"}:
        return _WS.sub(" ", comparable(raw))
    return comparable(raw)


def outcome_severity(outcome: ReconciliationOutcome) -> FindingSeverity:
    if outcome == ReconciliationOutcome.MATCH:
        return FindingSeverity.INFO
    if outcome == ReconciliationOutcome.MISSING_DATA:
        return FindingSeverity.WARNING
    return FindingSeverity.MANUAL_REVIEW


def outcome_validation(outcome: ReconciliationOutcome) -> ValidationOutcome:
    if outcome == ReconciliationOutcome.MATCH:
        return ValidationOutcome.PASS
    if outcome == ReconciliationOutcome.MISSING_DATA:
        return ValidationOutcome.WARNING
    return ValidationOutcome.MANUAL_REVIEW


def fingerprint_for(
    field_name: str,
    outcome: ReconciliationOutcome,
    values: list[DiscrepancyValue],
) -> str:
    parts = [field_name, outcome.value]
    for v in sorted(values, key=lambda x: (x.document_id, x.value)):
        norm = v.normalized_value or normalize_for_field(field_name, v.value)
        parts.append(f"{v.document_id}:{norm}")
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return digest[:40]


@dataclass
class DocMeta:
    document_id: str
    document_name: str
    sha256: str = ""
    requirement_code: str = ""


@dataclass
class ReconciliationCompareResult:
    drafts: list[DiscrepancyDraft] = field(default_factory=list)
    input_fingerprint: str = ""


class BasicReconciliationModule(ReconciliationModule):
    name = "reconciliation"

    def capability(self) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.AVAILABLE,
            message=(
                "Cross-document compare of identity/location/date/area fields with "
                "MATCH / MISMATCH / MISSING_DATA / POSSIBLE_DUPLICATE / MANUAL_REVIEW outcomes. "
                "Never labels fraud."
            ),
            data={"fields": sorted(RECONCILE_FIELDS), "engine": ENGINE_VERSION},
        )

    def reconcile(self, records: list[FieldRecord]) -> list[DiscrepancyDraft]:
        """Backward-compatible: returns non-MATCH drafts only (for the rule engine)."""
        result = self.compare(records, documents=[])
        return [d for d in result.drafts if d.outcome != ReconciliationOutcome.MATCH]

    def compare(
        self,
        records: list[FieldRecord],
        *,
        documents: Optional[list[DocMeta]] = None,
    ) -> ReconciliationCompareResult:
        documents = documents or []
        drafts: list[DiscrepancyDraft] = []

        by_field: dict[str, list[FieldRecord]] = defaultdict(list)
        for r in records:
            if r.field_name in RECONCILE_FIELDS and (r.value or "").strip():
                by_field[r.field_name].append(r)

        doc_ids_with_fields = {r.document_id for r in records}
        # Prefer full document list when provided (for missing-data + duplicates)
        all_doc_ids = {d.document_id for d in documents} or doc_ids_with_fields

        for field_name, recs in sorted(by_field.items()):
            drafts.append(self._compare_field(field_name, recs, all_doc_ids))

        # POSSIBLE_DUPLICATE: identical content hashes across distinct documents
        drafts.extend(self._duplicate_documents(documents))

        fp_src = []
        for d in drafts:
            fp_src.append(d.fingerprint or fingerprint_for(d.field_name, d.outcome, d.values))
        for r in sorted(records, key=lambda x: (x.field_name, x.document_id, x.value)):
            fp_src.append(f"{r.field_name}:{r.document_id}:{normalize_for_field(r.field_name, r.value)}")
        for d in sorted(documents, key=lambda x: x.document_id):
            fp_src.append(f"doc:{d.document_id}:{d.sha256}")
        input_fp = hashlib.sha256("\n".join(fp_src).encode("utf-8")).hexdigest()[:40]

        return ReconciliationCompareResult(drafts=drafts, input_fingerprint=input_fp)

    def _compare_field(
        self,
        field_name: str,
        recs: list[FieldRecord],
        all_doc_ids: set[str],
    ) -> DiscrepancyDraft:
        label = field_label(field_name)
        values = [
            DiscrepancyValue(
                document_id=r.document_id,
                document_name=r.document_name,
                value=r.value,
                page=r.page_reference,
                page_number=r.page_number,
                extracted_field_id=r.extracted_field_id,
                normalized_value=normalize_for_field(field_name, r.value),
                evidence_snippet=r.evidence_snippet,
            )
            for r in recs
        ]

        docs_with_value = {r.document_id for r in recs}
        norms = {normalize_for_field(field_name, r.value) for r in recs}
        raws = {(r.value or "").strip() for r in recs}

        # Missing on other documents that have any extractions in this application
        missing_docs = all_doc_ids - docs_with_value
        if len(docs_with_value) >= 1 and len(all_doc_ids) >= 2 and missing_docs and len(norms) <= 1:
            # Present on some docs, absent on others — MISSING_DATA (still attach present values)
            outcome = ReconciliationOutcome.MISSING_DATA
            title = f"{label} missing on some documents"
            description = (
                f"'{label}' was extracted from {len(docs_with_value)} document(s) but is absent "
                f"from {len(missing_docs)} other document(s). Not a fraud determination — "
                "officer may request the missing value or waive."
            )
            match_kind = None
        elif len(docs_with_value) < 2:
            # Only one document has this field overall — informational MATCH (nothing to conflict)
            outcome = ReconciliationOutcome.MATCH
            title = f"{label} present on a single document"
            description = f"Only one document provided '{label}'; no cross-document conflict."
            match_kind = "exact"
        elif field_name in DATE_RECONCILE_FIELDS and self._ambiguous_dates(recs):
            outcome = ReconciliationOutcome.MANUAL_REVIEW
            title = f"{label} date values need manual review"
            description = (
                f"Date values for '{label}' could not be normalized unambiguously across documents. "
                "Formatting may differ or the date may be a range. Requires officer confirmation — "
                "not labeled as fraud."
            )
            match_kind = None
        elif len(norms) == 1:
            outcome = ReconciliationOutcome.MATCH
            if len(raws) == 1:
                match_kind = "exact"
                title = f"{label} matches across documents"
                description = f"Exact match for '{label}' across {len(docs_with_value)} documents."
            else:
                match_kind = "normalization"
                title = f"{label} matches after normalization"
                description = (
                    f"Raw values for '{label}' differ in formatting/punctuation/case but normalize "
                    f"to the same comparable value across {len(docs_with_value)} documents."
                )
        else:
            outcome = ReconciliationOutcome.MISMATCH
            match_kind = None
            title = f"{label} differs across documents"
            description = (
                f"Extracted values for '{label}' conflict across documents after normalization. "
                "Requires officer confirmation — not a fraud determination."
            )

        fp = fingerprint_for(field_name, outcome, values)
        return DiscrepancyDraft(
            field_name=field_name,
            values=values,
            outcome=outcome,
            severity=outcome_severity(outcome),
            validation_outcome=outcome_validation(outcome),
            title=title,
            description=description,
            match_kind=match_kind,
            fingerprint=fp,
        )

    def _ambiguous_dates(self, recs: list[FieldRecord]) -> bool:
        """True when ≥2 docs have date-like strings that do not all normalize to one ISO date,
        and at least one value failed ISO parse (ambiguous formatting)."""
        from app.document_processing.field_extractor import parse_date

        parsed: list[Optional[str]] = []
        for r in recs:
            parsed.append(parse_date((r.value or "").strip()))
        if any(p is None for p in parsed) and len({comparable(r.value) for r in recs}) >= 2:
            return True
        return False

    def _duplicate_documents(self, documents: list[DocMeta]) -> list[DiscrepancyDraft]:
        by_hash: dict[str, list[DocMeta]] = defaultdict(list)
        for d in documents:
            if d.sha256:
                by_hash[d.sha256].append(d)
        out: list[DiscrepancyDraft] = []
        for sha, group in sorted(by_hash.items(), key=lambda x: x[0]):
            if len(group) < 2:
                continue
            values = [
                DiscrepancyValue(
                    document_id=d.document_id,
                    document_name=d.document_name,
                    value=f"sha256:{sha[:16]}…",
                    normalized_value=sha,
                    evidence_snippet=f"Identical file checksum ({sha[:16]}…)",
                )
                for d in group
            ]
            outcome = ReconciliationOutcome.POSSIBLE_DUPLICATE
            fp = fingerprint_for("_document_hash", outcome, values)
            out.append(
                DiscrepancyDraft(
                    field_name="_document_hash",
                    values=values,
                    outcome=outcome,
                    severity=outcome_severity(outcome),
                    validation_outcome=outcome_validation(outcome),
                    title="Possible duplicate documents",
                    description=(
                        f"{len(group)} documents share the same content checksum. "
                        "This may be an accidental re-upload — not labeled as fraud."
                    ),
                    match_kind=None,
                    fingerprint=fp,
                )
            )
        return out
