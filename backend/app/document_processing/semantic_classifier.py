"""Best-effort semantic document-category classifier (deterministic signals only)."""

from __future__ import annotations

import re
from collections import Counter

from app.document_processing.intelligence_types import PageText, SemanticClassification
from app.models.enums import SemanticDocumentCategory

# Maps to applicant requirement codes for mismatch checks
CATEGORY_TO_REQUIREMENT: dict[SemanticDocumentCategory, set[str]] = {
    SemanticDocumentCategory.AFFIDAVIT: {"AFFIDAVIT"},
    SemanticDocumentCategory.AFFIDAVIT_2: {"AFFIDAVIT_2"},
    SemanticDocumentCategory.LAND_OR_LEASE: {"LAND_OWNERSHIP"},
    SemanticDocumentCategory.AFFILIATION: {"AFFILIATION"},
    SemanticDocumentCategory.BUILDING: {"BUILDING_PLAN", "OCCUPANCY_CERTIFICATE"},
    SemanticDocumentCategory.FIRE_NOC: {"FIRE_NOC"},
    SemanticDocumentCategory.TRUST_OR_SOCIETY: {"AFFIDAVIT", "LAND_OWNERSHIP"},
    SemanticDocumentCategory.AICTE_PAYMENT_RECEIPT: {"AICTE_PAYMENT_RECEIPT"},
    SemanticDocumentCategory.AUDITED_ACCOUNTS: {"AUDITED_ACCOUNTS"},
    SemanticDocumentCategory.STRUCTURAL_STABILITY: {"STRUCTURAL_STABILITY"},
    SemanticDocumentCategory.SATELLITE_MAP: {"SATELLITE_MAP"},
}

REQUIREMENT_TO_CATEGORY: dict[str, SemanticDocumentCategory] = {
    "AFFIDAVIT": SemanticDocumentCategory.AFFIDAVIT,
    "AFFIDAVIT_2": SemanticDocumentCategory.AFFIDAVIT_2,
    "LAND_OWNERSHIP": SemanticDocumentCategory.LAND_OR_LEASE,
    "AFFILIATION": SemanticDocumentCategory.AFFILIATION,
    "BUILDING_PLAN": SemanticDocumentCategory.BUILDING,
    "FIRE_NOC": SemanticDocumentCategory.FIRE_NOC,
    "OCCUPANCY_CERTIFICATE": SemanticDocumentCategory.BUILDING,
    "STRUCTURAL_STABILITY": SemanticDocumentCategory.STRUCTURAL_STABILITY,
    "AICTE_PAYMENT_RECEIPT": SemanticDocumentCategory.AICTE_PAYMENT_RECEIPT,
    "SATELLITE_MAP": SemanticDocumentCategory.SATELLITE_MAP,
    "AUDITED_ACCOUNTS": SemanticDocumentCategory.AUDITED_ACCOUNTS,
}

KEYWORDS: dict[SemanticDocumentCategory, frozenset[str]] = {
    SemanticDocumentCategory.AFFIDAVIT: frozenset(
        {"affidavit", "undertaking", "solemnly", "deponent", "sworn"}
    ),
    SemanticDocumentCategory.AFFIDAVIT_2: frozenset(
        {"estamp", "stamp", "notary", "stamppaper", "estamped"}
    ),
    SemanticDocumentCategory.LAND_OR_LEASE: frozenset(
        {"lease", "deed", "survey", "land", "ownership", "parcel", "acre", "hectare"}
    ),
    SemanticDocumentCategory.FIRE_NOC: frozenset({"fire", "noc", "firefighting", "fire safety"}),
    SemanticDocumentCategory.BUILDING: frozenset(
        {"building", "plan", "blueprint", "floor", "architect", "construction"}
    ),
    SemanticDocumentCategory.TRUST_OR_SOCIETY: frozenset(
        {"trust", "society", "registration of societies", "trustee"}
    ),
    SemanticDocumentCategory.AFFILIATION: frozenset(
        {"affiliation", "affiliated", "university", "approval"}
    ),
    SemanticDocumentCategory.AICTE_PAYMENT_RECEIPT: frozenset(
        {"payment", "receipt", "challan", "transaction", "fee"}
    ),
    SemanticDocumentCategory.AUDITED_ACCOUNTS: frozenset(
        {"audited", "accounts", "balancesheet", "financial", "chartered"}
    ),
    SemanticDocumentCategory.STRUCTURAL_STABILITY: frozenset(
        {"structural", "stability", "seismic"}
    ),
    SemanticDocumentCategory.SATELLITE_MAP: frozenset(
        {"satellite", "geotag", "geotagged", "geolocation"}
    ),
}

# Marathi / Hindi (Devanagari) signals. The ASCII tokenizer below cannot see these, so they are
# matched as plain substrings of the OCR/text blob. Deliberately small and unambiguous.
DEVANAGARI_KEYWORDS: dict[SemanticDocumentCategory, frozenset[str]] = {
    SemanticDocumentCategory.AFFIDAVIT: frozenset(
        {"प्रतिज्ञापत्र", "शपथपत्र", "शपथ पत्र", "हमीपत्र", "हलफनामा"}
    ),
    SemanticDocumentCategory.LAND_OR_LEASE: frozenset({"भाडेपट्टा", "खरेदीखत", "सातबारा", "७/१२"}),
    SemanticDocumentCategory.FIRE_NOC: frozenset({"अग्निशमन", "अग्निशामक"}),
}

_TOKEN = re.compile(r"[a-z0-9]+")


class SemanticDocumentClassifier:
    name = "semantic_classifier"

    def classify(
        self,
        *,
        file_name: str,
        pages: list[PageText],
        selected_requirement_code: str | None = None,
    ) -> SemanticClassification:
        text_blob = " ".join(p.text for p in pages).lower()
        name_blob = file_name.lower()
        tokens = Counter(_TOKEN.findall(text_blob + " " + name_blob))

        scores: dict[SemanticDocumentCategory, int] = {}
        hit_details: dict[str, list[str]] = {}
        for cat, words in KEYWORDS.items():
            hits = [w for w in words if tokens.get(w, 0) > 0 or w in name_blob]
            for dev_word in DEVANAGARI_KEYWORDS.get(cat, ()):
                if dev_word in text_blob or dev_word in name_blob:
                    hits.append(dev_word)
            scores[cat] = len(hits)
            if hits:
                hit_details[cat.value] = hits

        best_score = max(scores.values(), default=0)
        if best_score == 0:
            return SemanticClassification(
                category=SemanticDocumentCategory.UNKNOWN,
                method="keyword_heuristic",
                confidence=None,
                signals={"selected_requirement": selected_requirement_code},
                rationale="Insufficient keyword evidence; category unknown.",
            )

        winners = [c for c, s in scores.items() if s == best_score]
        if len(winners) > 1:
            return SemanticClassification(
                category=SemanticDocumentCategory.UNKNOWN,
                method="keyword_heuristic",
                confidence=None,
                signals={"ambiguous": [w.value for w in winners], "hits": hit_details},
                rationale=f"Ambiguous between {', '.join(w.value for w in winners)}.",
            )

        winner = winners[0]
        # Confidence only when we have a clear score margin — still a heuristic, so keep modest
        total_hits = sum(scores.values()) or 1
        conf = round(best_score / total_hits, 3)
        # Cap: keyword heuristics are weak signals
        conf = min(conf, 0.75)

        return SemanticClassification(
            category=winner,
            method="keyword_heuristic",
            confidence=conf,
            signals={"hits": hit_details.get(winner.value, []), "scores": {k.value: v for k, v in scores.items()}},
            rationale=f"Keywords suggest {winner.value}.",
        )


def is_category_mismatch(
    predicted: SemanticDocumentCategory, selected_requirement_code: str | None
) -> bool:
    if not selected_requirement_code or predicted in (
        SemanticDocumentCategory.UNKNOWN,
        SemanticDocumentCategory.OTHER,
    ):
        return False
    expected = REQUIREMENT_TO_CATEGORY.get(selected_requirement_code)
    if expected is None:
        return False
    if predicted == expected:
        return False
    # A predicted category may legitimately serve several requirement codes
    # (e.g. a trust/society document supports an affidavit or a land document).
    if selected_requirement_code in CATEGORY_TO_REQUIREMENT.get(predicted, set()):
        return False
    # Both affidavit requirements are affidavits to a keyword classifier.
    affidavits = {SemanticDocumentCategory.AFFIDAVIT, SemanticDocumentCategory.AFFIDAVIT_2}
    if predicted in affidavits and expected in affidavits:
        return False
    return True
