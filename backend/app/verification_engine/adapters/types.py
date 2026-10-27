from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from app.models.enums import VerificationSource, VerificationStatus

VerificationModeLiteral = Literal["REAL", "SIMULATED"]


@dataclass
class AdapterContext:
    document_id: str
    document_version_id: str
    requirement_code: str
    file_path: str | None
    mime_type: str
    fields: dict[str, str]
    subject: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdapterResult:
    adapter: str
    claim_type: str
    status: VerificationStatus
    source: VerificationSource
    detail: str
    checked_at: datetime | None
    evidence: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)
    # Addendum / Phase 1 fields
    mode: VerificationModeLiteral = "REAL"
    official_verification: bool = False
    provider_name: str = ""
    provider_reference_id: str | None = None
    request_summary: str = ""
    response_summary: str = ""
    scope_of_confirmation: str = ""

    def __post_init__(self) -> None:
        if self.source == VerificationSource.SIMULATED_DEV and self.mode == "REAL":
            self.mode = "SIMULATED"
        if self.mode == "SIMULATED" and self.official_verification:
            raise ValueError("official_verification must be False when mode is SIMULATED")
        if not self.provider_name:
            self.provider_name = self.adapter
        if not self.response_summary:
            self.response_summary = self.detail
        if self.mode == "SIMULATED":
            self.official_verification = False
