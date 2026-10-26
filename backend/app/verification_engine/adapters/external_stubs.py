"""Authorized-source adapters for payments, building, fire, engineer, auditor.

No live authorized AICTE/municipal/council connectors are configured in this build.
Every call returns SOURCE_UNAVAILABLE or MANUAL_VERIFICATION_REQUIRED — never a
fabricated verified_by_source result.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import settings
from app.integrations.registry import get_verification_adapter
from app.models.enums import VerificationSource, VerificationStatus
from app.verification_engine.adapters.types import AdapterContext, AdapterResult

_ADAPTER_META = {
    "aicte_payment": {
        "claim_type": "payment_receipt",
        "label": "AICTE payment receipt registry",
        "detail": "No authorized AICTE payment verification API is configured in this build.",
    },
    "building_permission": {
        "claim_type": "building_permission",
        "label": "Building permission / occupancy authority",
        "detail": "No authorized municipal/building-permission connector is configured.",
    },
    "fire_certificate": {
        "claim_type": "fire_certificate",
        "label": "Fire safety certificate authority",
        "detail": "No authorized fire-service certificate connector is configured.",
    },
    "engineer_credential": {
        "claim_type": "engineer_credential",
        "label": "Structural engineer credential registry",
        "detail": "No authorized engineer license registry connector is configured.",
    },
    "auditor_credential": {
        "claim_type": "auditor_credential",
        "label": "Auditor credential registry",
        "detail": "No authorized auditor/CA registry connector is configured.",
    },
}


def verify_authorized_stub(adapter_id: str, ctx: AdapterContext) -> AdapterResult:
    now = datetime.now(timezone.utc)
    meta = _ADAPTER_META.get(adapter_id)
    if not meta:
        return AdapterResult(
            adapter=adapter_id,
            claim_type="unknown",
            status=VerificationStatus.SOURCE_UNAVAILABLE,
            source=VerificationSource.AUTHORIZED_LIVE,
            detail=f"Unknown adapter '{adapter_id}'.",
            checked_at=now,
        )

    # If global live verification is on, still no connector — honest unavailable.
    # If mock adapter mode, label simulated explicitly when ENABLE_LIVE is false
    # and a simulated path is requested via settings.
    if settings.enable_live_verification:
        return AdapterResult(
            adapter=adapter_id,
            claim_type=meta["claim_type"],
            status=VerificationStatus.SOURCE_UNAVAILABLE,
            source=VerificationSource.AUTHORIZED_LIVE,
            detail=meta["detail"] + " Live flag is on but connector is not implemented.",
            checked_at=now,
            evidence={"fields_keys": sorted(ctx.fields.keys())},
            limitations=["Authorized live connector not implemented"],
        )

    # Optional: if demo mock adapter is active for app-level claims, still do NOT
    # invent source-confirmed payment/credential results for Phase 7 document adapters.
    _ = get_verification_adapter()
    return AdapterResult(
        adapter=adapter_id,
        claim_type=meta["claim_type"],
        status=VerificationStatus.SOURCE_UNAVAILABLE,
        source=VerificationSource.AUTHORIZED_LIVE,
        detail=meta["detail"] + " Returning SOURCE_UNAVAILABLE (not simulated as verified).",
        checked_at=now,
        evidence={"label": meta["label"], "fields_keys": sorted(ctx.fields.keys())},
        limitations=[
            "No authorized source integrated",
            "Layer 1 pass must not be treated as authenticity confirmation",
        ],
    )
