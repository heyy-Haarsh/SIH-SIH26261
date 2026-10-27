from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.schemas.common import CamelModel


class ExtractionFieldOut(CamelModel):
    id: str
    field_name: str
    value: str
    raw_value: str
    normalized_value: Optional[str] = None
    confidence: Optional[float] = None
    ocr_confidence: Optional[float] = None
    page_number: Optional[int] = None
    page_reference: Optional[str] = None
    bbox: Optional[dict[str, float]] = None
    coordinate_space: Optional[str] = None
    method: str
    review_status: str
    corrected_value: Optional[str] = None
    is_conflict: bool = False
    candidate_values: list[dict[str, Any]] = Field(default_factory=list)
    unit: Optional[str] = None
    source_document_id: str
    source_document_version_id: str


class ExtractionRunOut(CamelModel):
    id: str
    document_version_id: str
    application_id: str
    validation_run_id: Optional[str] = None
    status: str
    content_kind: str
    selected_category: Optional[str] = None
    predicted_category: str
    category_confidence: Optional[float] = None
    category_method: str = ""
    category_signals: dict[str, Any] = Field(default_factory=dict)
    category_mismatch: bool = False
    engine_version: str
    page_count: Optional[int] = None
    pages_with_text: int = 0
    pages_ocr: int = 0
    warnings: list[str] = Field(default_factory=list)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    stage_timings_ms: dict[str, int] = Field(default_factory=dict)
    ocr_available: bool = False
    ocr_languages: str = "eng"
    created_at: datetime
    completed_at: Optional[datetime] = None
    fields: list[ExtractionFieldOut] = Field(default_factory=list)


class ExtractionStartIn(BaseModel):
    force: bool = False
    run_validation_after: bool = True


class FieldCorrectionIn(BaseModel):
    corrected_value: str


class OcrCapabilityOut(CamelModel):
    enabled: bool
    available: bool
    message: str
    pytesseract_installed: bool = False
    tesseract_cmd_found: bool = False
    tesseract_version: Optional[str] = None
    languages_requested: list[str] = Field(default_factory=list)
    languages_available: list[str] = Field(default_factory=list)
    languages_missing: list[str] = Field(default_factory=list)
    languages_usable: list[str] = Field(default_factory=list)
    marathi_supported: bool = False
