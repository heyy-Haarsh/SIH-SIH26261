"""Deterministic structured field extraction from page text.

Confidence is left unavailable (None) for regex/key-value matches — never fabricated.
OCR confidence may be attached separately when the source page was OCR'd.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Optional

from app.document_processing.intelligence_types import BBox, FieldCandidate, PageText
from app.models.enums import ExtractionMethod

_KEY_ALIASES: dict[str, str] = {
    "institution name": "institution_name",
    "name of institution": "institution_name",
    "college name": "institution_name",
    "organization name": "institution_name",
    "name of the college": "institution_name",
    "registration number": "registration_number",
    "registration no": "registration_number",
    "certificate number": "certificate_number",
    "certificate no": "certificate_number",
    "reference number": "reference_number",
    "ref no": "reference_number",
    "ref. no": "reference_number",
    "valid until": "valid_until",
    "valid till": "valid_until",
    "valid upto": "valid_until",
    "validity": "valid_until",
    "expiry date": "expiry_date",
    "date of expiry": "expiry_date",
    "expires on": "expiry_date",
    "issue date": "issue_date",
    "date of issue": "issue_date",
    "issued on": "issue_date",
    "issuing authority": "issuing_authority",
    "issued by": "issuing_authority",
    "land area": "land_area",
    "area": "land_area",
    "survey number": "survey_number",
    "survey no": "survey_number",
    "parcel number": "survey_number",
    "plot number": "plot_number",
    "plot no": "plot_number",
    "trust name": "trust_name",
    "society name": "trust_name",
    "document type": "document_type",
    "address": "address",
    "registered address": "registered_address",
    "institution address": "address",
    "college address": "address",
}

DATE_FIELDS = frozenset({"valid_until", "expiry_date", "issue_date"})
ID_FIELDS = frozenset({"registration_number", "certificate_number", "reference_number", "survey_number"})

_LINE_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 ()_.\-/]{1,48}?)\s*[:=\-]\s*(.+?)\s*$")
_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y", "%d %b %Y", "%d %B %Y")
_AREA_RE = re.compile(
    r"(?P<value>\d+(?:[.,]\d+)?)\s*(?P<unit>acres?|hectares?|sq\.?\s*m(?:eters?)?|sq\.?\s*ft|sqft)",
    re.I,
)
_FILENAME_VALID_UNTIL = re.compile(
    r"valid[_\- ]?(?:until|till|upto)[_\- ]?(\d{4})[-_]?(\d{2})[-_]?(\d{2})", re.I
)

MAX_FIELDS = 40


def parse_date(value: str) -> Optional[str]:
    """Return ISO date only when parsing is unambiguous; else None (preserve raw)."""
    value = value.strip()
    # Reject ranges / ambiguous multi-date strings
    if " to " in value.lower() or " - " in value and value.count("-") > 2:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _normalize_label(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()


def _find_bbox_for_value(page: PageText, value: str) -> Optional[BBox]:
    needle = value.strip().casefold()
    if not needle:
        return None
    for b in page.blocks:
        if needle in (b.get("text") or "").casefold():
            box = b.get("bbox")
            if box and len(box) == 4:
                return BBox(
                    x0=float(box[0]),
                    y0=float(box[1]),
                    x1=float(box[2]),
                    y1=float(box[3]),
                    coordinate_space=b.get("coordinate_space") or "pdf_page_points",
                )
    return None


class FieldExtractor:
    name = "field_extractor"

    def extract_from_pages(
        self, pages: list[PageText], *, file_name: str = ""
    ) -> list[FieldCandidate]:
        by_field: dict[str, list[FieldCandidate]] = defaultdict(list)

        for page in pages:
            for lineno, line in enumerate(page.text.splitlines()[:800], start=1):
                m = _LINE_RE.match(line)
                if not m:
                    continue
                key = _KEY_ALIASES.get(_normalize_label(m.group(1)))
                if not key:
                    continue
                raw = m.group(2).strip()
                if not raw:
                    continue
                normalized = None
                unit = None
                if key in DATE_FIELDS:
                    normalized = parse_date(raw)
                elif key == "land_area":
                    am = _AREA_RE.search(raw)
                    if am:
                        raw_num = am.group("value").replace(",", "")
                        # Preserve exact numeric text; do not strip leading zeros from IDs
                        normalized = raw_num
                        unit = re.sub(r"\s+", " ", am.group("unit").lower())
                # Never strip leading zeros from identifier fields
                if key in ID_FIELDS:
                    normalized = raw  # keep as-is

                method = (
                    ExtractionMethod.OCR
                    if page.source == "ocr"
                    else ExtractionMethod.PDF_TEXT
                    if page.source == "pdf_text"
                    else ExtractionMethod.TEXT_KEY_VALUE
                )
                cand = FieldCandidate(
                    field_name=key,
                    raw_value=raw,
                    normalized_value=normalized,
                    method=method,
                    confidence=None,  # deterministic regex — no fabricated confidence
                    ocr_confidence=page.ocr_confidence if page.source == "ocr" else None,
                    page_number=page.page_number,
                    page_reference=f"p.{page.page_number} L{lineno}",
                    bbox=_find_bbox_for_value(page, raw),
                    unit=unit,
                )
                by_field[key].append(cand)

        # Filename metadata (no confidence)
        m = _FILENAME_VALID_UNTIL.search(file_name or "")
        if m and "valid_until" not in by_field:
            iso = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            by_field["valid_until"].append(
                FieldCandidate(
                    field_name="valid_until",
                    raw_value=iso,
                    normalized_value=iso,
                    method=ExtractionMethod.FILENAME_METADATA,
                    confidence=None,
                    page_reference=None,
                )
            )

        # Collapse conflicts: keep all candidates marked via first + extras
        results: list[FieldCandidate] = []
        for key, cands in by_field.items():
            # Deduplicate identical raw values
            unique: list[FieldCandidate] = []
            seen: set[str] = set()
            for c in cands:
                marker = c.raw_value.casefold()
                if marker in seen:
                    continue
                seen.add(marker)
                unique.append(c)
            if len(unique) == 1:
                results.append(unique[0])
            else:
                # Conflicting values — mark for review; do not silently pick one
                primary = unique[0]
                primary.confidence = None
                results.append(primary)
                # Store siblings as additional entries with same name for orchestrator to merge
                for extra in unique[1:]:
                    results.append(extra)
            if len(results) >= MAX_FIELDS:
                break
        return results
