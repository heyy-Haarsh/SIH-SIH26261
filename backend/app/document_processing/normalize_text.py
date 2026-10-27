"""Transliteration / ASCII normalization — never overwrites the raw value."""

from __future__ import annotations

import re
import unicodedata


def ascii_fold(value: str) -> str:
    """NFKD fold to ASCII letters/digits/spaces for fuzzy compare."""
    if not value:
        return value
    # Optional Indic → Latin when library present
    try:
        from indic_transliteration import sanscript  # type: ignore
        from indic_transliteration.sanscript import transliterate  # type: ignore

        # Heuristic: if Devanagari present, transliterate to ITRANS then fold
        if re.search(r"[\u0900-\u097F]", value):
            value = transliterate(value, sanscript.DEVANAGARI, sanscript.ITRANS)
    except ImportError:
        pass
    folded = unicodedata.normalize("NFKD", value)
    folded = folded.encode("ascii", "ignore").decode("ascii")
    folded = re.sub(r"\s+", " ", folded).strip().lower()
    return folded


def compute_normalized_value(raw: str, *, already: str | None = None) -> str | None:
    if already:
        return already
    if not raw or not raw.strip():
        return None
    norm = ascii_fold(raw)
    return norm or None
