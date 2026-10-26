from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models.enums import VerificationSource, VerificationStatus


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
