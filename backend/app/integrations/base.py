"""External verification adapter interface.

Statuses are truthful: an adapter must say where an answer came from
(``VerificationSource``) and use ``source_unavailable`` rather than inventing a
result when it cannot reach an authorised source. No real AICTE or issuing
authority API is integrated in this build.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from app.models.enums import VerificationSource, VerificationStatus

__all__ = [
    "VerificationAdapter",
    "VerificationClaim",
    "VerificationOutcome",
    "VerificationSource",
    "VerificationStatus",
]


@dataclass
class VerificationClaim:
    claim_type: str  # e.g. "institution_registration", "document_authenticity"
    claim: str  # human-readable statement being checked
    subject: dict[str, Any] = field(default_factory=dict)  # identifiers (institution code, sha256, ...)
    document_id: Optional[str] = None


@dataclass
class VerificationOutcome:
    status: VerificationStatus
    source: VerificationSource
    detail: str
    checked_at: Optional[datetime]
    adapter: str


class VerificationAdapter(ABC):
    name: str = "adapter"
    source: VerificationSource = VerificationSource.SIMULATED_DEV
    is_live: bool = False

    @abstractmethod
    def verify(self, claim: VerificationClaim) -> VerificationOutcome:
        """Check a claim and return a truthful outcome."""

    @abstractmethod
    def describe(self) -> dict[str, Any]:
        """Admin-facing description of this integration's real state."""
