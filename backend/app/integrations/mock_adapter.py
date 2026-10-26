"""Development mock adapter. Results are SIMULATED - no external system is contacted."""

from typing import Any

from app.integrations.base import (
    VerificationAdapter,
    VerificationClaim,
    VerificationOutcome,
    VerificationSource,
    VerificationStatus,
)
from app.models.base import utcnow


class MockVerificationAdapter(VerificationAdapter):
    name = "mock_adapter"
    source = VerificationSource.SIMULATED_DEV
    is_live = False

    def verify(self, claim: VerificationClaim) -> VerificationOutcome:
        return VerificationOutcome(
            status=VerificationStatus.SIMULATED_RESULT,
            source=VerificationSource.SIMULATED_DEV,
            detail=(
                "SIMULATED development result. No authorised external source was contacted, "
                "so this does not confirm the claim."
            ),
            checked_at=utcnow(),
            adapter=self.name,
        )

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": "mock",
            "live": False,
            "source": self.source.value,
            "status": "simulated_dev",
            "detail": "Returns simulated results for development and demos only.",
        }
