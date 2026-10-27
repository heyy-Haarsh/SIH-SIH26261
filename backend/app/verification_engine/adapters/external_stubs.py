"""Authorized-source adapters for payments, building, fire, engineer, auditor.

Prefer HTTP simulated-issuer connectors via the registry. This module remains
as a last-resort stub when no HTTP client is configured — always honest
SOURCE_UNAVAILABLE / never fabricated verified_by_source.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import settings
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
    "affidavit_estamp": {
        "claim_type": "estamp",
        "label": "Affidavit e-stamp registry",
        "detail": "No authorized e-stamp verification API is configured in this build.",
    },
}


def verify_authorized_stub(adapter_id: str, ctx: AdapterContext) -> AdapterResult:
    """Fallback when HTTP simulated issuer is not used."""
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
            mode="REAL",
            official_verification=False,
            provider_name=adapter_id,
            request_summary="stub",
            response_summary="unknown adapter",
            scope_of_confirmation="none",
        )

    detail = meta["detail"]
    if settings.enable_live_verification:
        detail += " Live flag is on but connector is not implemented."
    else:
        detail += " Returning SOURCE_UNAVAILABLE (not simulated as verified)."

    return AdapterResult(
        adapter=adapter_id,
        claim_type=meta["claim_type"],
        status=VerificationStatus.SOURCE_UNAVAILABLE,
        source=VerificationSource.AUTHORIZED_LIVE,
        detail=detail,
        checked_at=now,
        mode="REAL",
        official_verification=False,
        provider_name=meta["label"],
        request_summary=f"stub fields={sorted(ctx.fields.keys())}",
        response_summary="source_unavailable",
        scope_of_confirmation="none — stub only",
        evidence={"label": meta["label"], "fields_keys": sorted(ctx.fields.keys())},
        limitations=[
            "No authorized source integrated",
            "Layer 1 pass must not be treated as authenticity confirmation",
            f"Configure {adapter_id} HTTP issuer or credentials to enable checks",
        ],
    )
