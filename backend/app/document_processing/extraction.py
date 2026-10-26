"""Modules 3 & 4: extraction and normalization.

AI/OCR extraction is NOT available. What exists:
  * deterministic ``Key: Value`` parsing of plain-text (.txt) uploads, restricted to a known key set
  * ``valid_until_YYYY-MM-DD`` style metadata in file names
Neither produces a confidence score (``None``), because neither is a scored model.
"""

import re
from datetime import date, datetime
from typing import Optional

from app.core.config import settings
from app.document_processing.interfaces import ExtractionModule, NormalizationModule
from app.document_processing.types import ExtractedFieldDraft, ModuleResult, ModuleStatus

# normalised label -> canonical field key
_KEY_ALIASES: dict[str, str] = {
    "institution name": "institution_name",
    "name of institution": "institution_name",
    "college name": "institution_name",
    "registration number": "registration_number",
    "registration no": "registration_number",
    "valid until": "valid_until",
    "valid till": "valid_until",
    "valid upto": "valid_until",
    "expiry date": "expiry_date",
    "date of expiry": "expiry_date",
    "expires on": "expiry_date",
    "issue date": "issue_date",
    "date of issue": "issue_date",
    "issued on": "issue_date",
    "issuing authority": "issuing_authority",
    "land area": "land_area",
    "land area acres": "land_area",
    "survey number": "survey_number",
    "trust name": "trust_name",
    "society name": "trust_name",
}
DATE_FIELDS = frozenset({"valid_until", "expiry_date", "issue_date"})

_LINE_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 ()_.\-/]{1,40}?)\s*[:=]\s*(.+?)\s*$")
_FILENAME_VALID_UNTIL = re.compile(r"valid[_\- ]?(?:until|till|upto)[_\- ]?(\d{4})[-_]?(\d{2})[-_]?(\d{2})", re.I)
MAX_LINES = 500
MAX_FIELDS = 30

_DATE_FORMATS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%d.%m.%Y")


def parse_date(value: str) -> Optional[date]:
    value = value.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def field_label(field_name: str) -> str:
    return field_name.replace("_", " ").title()


class LocalExtractionModule(ExtractionModule):
    name = "extraction"

    def capability(self) -> ModuleResult:
        msg = (
            "AI/OCR extraction is not available. Only deterministic key:value parsing of .txt "
            "files and file-name metadata is performed."
        )
        if settings.enable_ai_extraction:
            msg += " (ENABLE_AI_EXTRACTION is set, but no AI provider is implemented in this build.)"
        return ModuleResult(module=self.name, status=ModuleStatus.LIMITED, message=msg)

    def extract(self, *, file_name: str, extension: str, content: bytes) -> list[ExtractedFieldDraft]:
        drafts: list[ExtractedFieldDraft] = []

        if extension == "txt":
            text = content.decode("utf-8", errors="replace")
            seen: set[str] = set()
            for lineno, line in enumerate(text.splitlines()[:MAX_LINES], start=1):
                m = _LINE_RE.match(line)
                if not m:
                    continue
                label = re.sub(r"[^a-z0-9]+", " ", m.group(1).lower()).strip()
                key = _KEY_ALIASES.get(label)
                if not key or key in seen:
                    continue
                seen.add(key)
                drafts.append(
                    ExtractedFieldDraft(
                        field_name=key,
                        value=m.group(2),
                        confidence=None,
                        page_reference=f"line {lineno}",
                        method="text_key_value",
                    )
                )
                if len(drafts) >= MAX_FIELDS:
                    break

        m = _FILENAME_VALID_UNTIL.search(file_name)
        if m and not any(d.field_name == "valid_until" for d in drafts):
            drafts.append(
                ExtractedFieldDraft(
                    field_name="valid_until",
                    value=f"{m.group(1)}-{m.group(2)}-{m.group(3)}",
                    confidence=None,
                    page_reference=None,
                    method="filename_metadata",
                )
            )
        return drafts


class BasicNormalizationModule(NormalizationModule):
    name = "normalization"

    def capability(self) -> ModuleResult:
        return ModuleResult(
            module=self.name,
            status=ModuleStatus.AVAILABLE,
            message="Whitespace trimming and ISO date normalisation.",
        )

    def normalize(self, fields: list[ExtractedFieldDraft]) -> list[ExtractedFieldDraft]:
        out: list[ExtractedFieldDraft] = []
        for f in fields:
            value = re.sub(r"\s+", " ", f.value).strip()
            if f.field_name in DATE_FIELDS:
                d = parse_date(value)
                if d:
                    value = d.isoformat()
            out.append(
                ExtractedFieldDraft(
                    field_name=f.field_name,
                    value=value,
                    confidence=f.confidence,
                    page_reference=f.page_reference,
                    method=f.method,
                )
            )
        return out
