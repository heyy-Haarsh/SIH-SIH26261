"""Module 5: basic cross-document reconciliation of extracted fields."""

import re
from collections import defaultdict

from app.document_processing.interfaces import ReconciliationModule
from app.document_processing.types import (
    DiscrepancyDraft,
    DiscrepancyValue,
    FieldRecord,
    ModuleResult,
    ModuleStatus,
)

# Identity-style fields that should agree across documents of one application.
RECONCILE_FIELDS = frozenset(
    {"institution_name", "registration_number", "trust_name", "land_area", "survey_number"}
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def comparable(value: str) -> str:
    return _NON_ALNUM.sub(" ", value.casefold()).strip()


class BasicReconciliationModule(ReconciliationModule):
    name = "reconciliation"

    def capability(self) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.AVAILABLE,
            message="Exact (case/punctuation-insensitive) comparison of identity fields across documents.",
        )

    def reconcile(self, records: list[FieldRecord]) -> list[DiscrepancyDraft]:
        by_field: dict[str, list[FieldRecord]] = defaultdict(list)
        for r in records:
            if r.field_name in RECONCILE_FIELDS:
                by_field[r.field_name].append(r)

        out: list[DiscrepancyDraft] = []
        for field_name, recs in sorted(by_field.items()):
            docs = {r.document_id for r in recs}
            distinct = {comparable(r.value) for r in recs}
            if len(docs) >= 2 and len(distinct) >= 2:
                out.append(
                    DiscrepancyDraft(
                        field_name=field_name,
                        values=[
                            DiscrepancyValue(r.document_id, r.document_name, r.value, r.page_reference)
                            for r in recs
                        ],
                    )
                )
        return out
