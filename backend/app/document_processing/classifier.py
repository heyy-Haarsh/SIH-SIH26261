"""Module 2: document classification.

Only a simple, transparent filename-keyword classifier exists. There is no
content-based or AI classifier; ``capability()`` says so. A filename is a weak
signal, so results carry no confidence score and are used only to raise
manual-review prompts, never to approve anything.
"""

import re
from typing import Optional

from app.document_processing.interfaces import ClassificationModule
from app.document_processing.types import ClassificationResult, ModuleResult, ModuleStatus

# requirement code -> filename tokens that suggest it
KEYWORDS: dict[str, frozenset[str]] = {
    "AFFIDAVIT": frozenset({"affidavit"}),
    "LAND_OWNERSHIP": frozenset({"land", "lease", "deed", "ownership", "title"}),
    "AFFILIATION": frozenset({"affiliation", "affiliated"}),
    "BUILDING_PLAN": frozenset({"building", "plan", "blueprint"}),
    "FIRE_NOC": frozenset({"fire", "noc"}),
    "AICTE_PAYMENT_RECEIPT": frozenset({"payment", "receipt", "challan", "transaction"}),
    "OCCUPANCY_CERTIFICATE": frozenset({"occupancy", "completion", "formd", "buildinglicense"}),
    "STRUCTURAL_STABILITY": frozenset({"structural", "stability", "engineer"}),
    "SATELLITE_MAP": frozenset({"satellite", "geotag", "geotagged", "map"}),
    "AUDITED_ACCOUNTS": frozenset({"audited", "accounts", "balance", "financial"}),
}

_TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


class NameBasedClassifier(ClassificationModule):
    name = "classification"

    def capability(self) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.LIMITED,
            message="Filename-keyword heuristic only; content-based/AI classification is not available.",
        )

    def classify(self, *, file_name: str, text: Optional[str] = None) -> ClassificationResult:
        tokens = {t for t in _TOKEN_SPLIT.split(file_name.lower()) if t}
        scores = {code: len(tokens & words) for code, words in KEYWORDS.items()}
        best = max(scores.values(), default=0)
        if best == 0:
            return ClassificationResult(
                status=ModuleStatus.UNAVAILABLE,
                method="filename_keyword",
                rationale="No known keywords found in the file name; classification unavailable.",
            )
        winners = [code for code, score in scores.items() if score == best]
        if len(winners) > 1:
            return ClassificationResult(
                status=ModuleStatus.UNAVAILABLE,
                method="filename_keyword",
                rationale=f"File name is ambiguous between {', '.join(sorted(winners))}.",
            )
        return ClassificationResult(
            status=ModuleStatus.LIMITED,
            label=winners[0],
            confidence=None,
            method="filename_keyword",
            rationale=f"File name keywords suggest {winners[0]} (heuristic, not content-verified).",
        )
