"""Adapter selection and integration status reporting."""

from typing import Any

from app.core.config import settings
from app.integrations.base import (
    VerificationAdapter,
    VerificationClaim,
    VerificationOutcome,
    VerificationSource,
    VerificationStatus,
)
from app.integrations.mock_adapter import MockVerificationAdapter


class UnconfiguredLiveAdapter(VerificationAdapter):
    """Placeholder used when live verification is requested but no connector exists.

    It never fabricates a result: every claim comes back ``source_unavailable``.
    """

    name = "aicte_live_unconfigured"
    source = VerificationSource.AUTHORIZED_LIVE
    is_live = True

    def verify(self, claim: VerificationClaim) -> VerificationOutcome:
        return VerificationOutcome(
            status=VerificationStatus.SOURCE_UNAVAILABLE,
            source=VerificationSource.AUTHORIZED_LIVE,
            detail="Live verification is enabled but no authorised connector is implemented or configured.",
            checked_at=None,
            adapter=self.name,
        )

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": "live_placeholder",
            "live": True,
            "source": self.source.value,
            "status": "not_configured",
            "detail": "No real connector exists in this build; all claims report source_unavailable.",
        }


def get_verification_adapter() -> VerificationAdapter:
    if settings.enable_live_verification:
        return UnconfiguredLiveAdapter()
    return MockVerificationAdapter()


def list_integrations() -> list[dict[str, Any]]:
    active = get_verification_adapter()
    return [
        {**active.describe(), "active": True},
        {
            "name": "ai_extraction",
            "kind": "ai",
            "live": False,
            "source": None,
            "active": False,
            "status": "not_available",
            "detail": "No AI/OCR provider is implemented in this build.",
        },
        {
            "name": "local_storage",
            "kind": "storage",
            "live": False,
            "source": VerificationSource.LOCAL_VALIDATION.value,
            "active": True,
            "status": "available",
            "detail": f"Local filesystem storage ({settings.storage_backend}).",
        },
    ]
