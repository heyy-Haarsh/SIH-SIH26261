"""DTOs for the document-intelligence pipeline (no ORM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.models.enums import (
    DocumentContentKind,
    ExtractionMethod,
    ExtractionRunStatus,
    SemanticDocumentCategory,
)


@dataclass
class BBox:
    """Page bounding box in PDF-point space, origin at top-left of the page."""

    x0: float
    y0: float
    x1: float
    y1: float
    coordinate_space: str = "pdf_page_points"


@dataclass
class PageText:
    page_number: int  # 1-based
    text: str
    source: str  # pdf_text | ocr | none
    char_count: int = 0
    ocr_confidence: Optional[float] = None  # mean word confidence 0-1 when OCR
    rotation: int = 0
    width: float = 0.0
    height: float = 0.0
    blocks: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class InspectResult:
    content_kind: DocumentContentKind
    page_count: Optional[int]
    encrypted: bool = False
    readable: bool = True
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    signals: dict[str, Any] = field(default_factory=dict)


@dataclass
class SemanticClassification:
    category: SemanticDocumentCategory
    method: str
    confidence: Optional[float]
    signals: dict[str, Any] = field(default_factory=dict)
    rationale: str = ""


@dataclass
class FieldCandidate:
    field_name: str
    raw_value: str
    normalized_value: Optional[str] = None
    method: ExtractionMethod = ExtractionMethod.REGEX
    confidence: Optional[float] = None  # None unless method supplies a real score
    ocr_confidence: Optional[float] = None
    page_number: Optional[int] = None
    page_reference: Optional[str] = None
    bbox: Optional[BBox] = None
    unit: Optional[str] = None
    raw_snippet: Optional[str] = None
    source: Optional[str] = None  # text_layer | ocr | llm | filename_metadata


@dataclass
class ExtractionOutcome:
    status: ExtractionRunStatus
    content_kind: DocumentContentKind
    pages: list[PageText] = field(default_factory=list)
    fields: list[FieldCandidate] = field(default_factory=list)
    semantic: Optional[SemanticClassification] = None
    warnings: list[str] = field(default_factory=list)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    stage_timings_ms: dict[str, int] = field(default_factory=dict)
    ocr_available: bool = False
    ocr_languages: str = "eng"
    page_count: Optional[int] = None
    pages_with_text: int = 0
    pages_ocr: int = 0
