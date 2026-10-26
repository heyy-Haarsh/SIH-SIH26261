"""Satellite-map geocoding via public Nominatim (OpenStreetMap).

Respects Nominatim usage policy: identifiable User-Agent, max 1 req/sec,
only when ENABLE_NOMINATIM_GEOCODE=true. Otherwise returns SOURCE_UNAVAILABLE.
"""

from __future__ import annotations

import math
import time
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.models.enums import VerificationSource, VerificationStatus
from app.verification_engine.adapters.types import AdapterContext, AdapterResult

_LAST_CALL_TS = 0.0


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def verify_geocode(ctx: AdapterContext) -> AdapterResult:
    now = datetime.now(timezone.utc)
    address = (ctx.fields.get("address") or "").strip()
    lat_s = (ctx.fields.get("latitude") or "").strip()
    lon_s = (ctx.fields.get("longitude") or "").strip()

    if not getattr(settings, "enable_nominatim_geocode", False):
        return AdapterResult(
            adapter="geocode_nominatim",
            claim_type="coordinate_consistency",
            status=VerificationStatus.SOURCE_UNAVAILABLE,
            source=VerificationSource.AUTHORIZED_LIVE,
            detail=(
                "Nominatim geocoding disabled (ENABLE_NOMINATIM_GEOCODE=false). "
                "No coordinate consistency check was performed."
            ),
            checked_at=now,
            limitations=["Public geocoder not enabled; respecting usage limits by default-off."],
        )

    if not address:
        return AdapterResult(
            adapter="geocode_nominatim",
            claim_type="coordinate_consistency",
            status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
            source=VerificationSource.LOCAL_VALIDATION,
            detail="No address field available to geocode.",
            checked_at=now,
            limitations=["Missing address"],
        )

    global _LAST_CALL_TS
    elapsed = time.monotonic() - _LAST_CALL_TS
    if elapsed < 1.05:
        time.sleep(1.05 - elapsed)

    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": address, "format": "json", "limit": 1},
                headers={"User-Agent": settings.nominatim_user_agent},
            )
            _LAST_CALL_TS = time.monotonic()
            if resp.status_code == 429:
                return AdapterResult(
                    adapter="geocode_nominatim",
                    claim_type="coordinate_consistency",
                    status=VerificationStatus.SOURCE_UNAVAILABLE,
                    source=VerificationSource.AUTHORIZED_LIVE,
                    detail="Nominatim rate limit exceeded (HTTP 429).",
                    checked_at=now,
                    limitations=["Rate limited"],
                )
            resp.raise_for_status()
            data = resp.json()
    except httpx.TimeoutException:
        return AdapterResult(
            adapter="geocode_nominatim",
            claim_type="coordinate_consistency",
            status=VerificationStatus.SOURCE_UNAVAILABLE,
            source=VerificationSource.AUTHORIZED_LIVE,
            detail="Nominatim request timed out.",
            checked_at=now,
            limitations=["Timeout"],
        )
    except Exception as exc:  # noqa: BLE001
        return AdapterResult(
            adapter="geocode_nominatim",
            claim_type="coordinate_consistency",
            status=VerificationStatus.SOURCE_UNAVAILABLE,
            source=VerificationSource.AUTHORIZED_LIVE,
            detail=f"Nominatim error: {exc}",
            checked_at=now,
            limitations=["Request failed"],
        )

    if not data:
        return AdapterResult(
            adapter="geocode_nominatim",
            claim_type="coordinate_consistency",
            status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
            source=VerificationSource.AUTHORIZED_LIVE,
            detail="Nominatim returned no results for the address.",
            checked_at=now,
            evidence={"address": address[:200]},
            limitations=["Geocode miss — not proof of falsified map"],
        )

    geo_lat = float(data[0]["lat"])
    geo_lon = float(data[0]["lon"])
    evidence = {
        "address": address[:200],
        "geocoded_lat": geo_lat,
        "geocoded_lon": geo_lon,
        "display_name": data[0].get("display_name"),
        "provider": "nominatim_osm",
    }

    if lat_s and lon_s:
        try:
            lat, lon = float(lat_s), float(lon_s)
        except ValueError:
            return AdapterResult(
                adapter="geocode_nominatim",
                claim_type="coordinate_consistency",
                status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
                source=VerificationSource.AUTHORIZED_LIVE,
                detail="Extracted coordinates could not be parsed as numbers.",
                checked_at=now,
                evidence=evidence,
            )
        dist = _haversine_m(lat, lon, geo_lat, geo_lon)
        evidence["extracted_lat"] = lat
        evidence["extracted_lon"] = lon
        evidence["distance_meters"] = round(dist, 1)
        threshold = float(getattr(settings, "geocode_mismatch_meters", 5000) or 5000)
        if dist > threshold:
            return AdapterResult(
                adapter="geocode_nominatim",
                claim_type="coordinate_consistency",
                status=VerificationStatus.MISMATCH_DETECTED,
                source=VerificationSource.AUTHORIZED_LIVE,
                detail=f"Extracted coordinates differ from geocoded address by {dist:.0f}m (threshold {threshold:.0f}m).",
                checked_at=now,
                evidence=evidence,
                limitations=["Public geocoder approximation; not a cadastral survey."],
            )
        return AdapterResult(
            adapter="geocode_nominatim",
            claim_type="coordinate_consistency",
            status=VerificationStatus.VERIFIED_BY_SOURCE,
            source=VerificationSource.AUTHORIZED_LIVE,
            detail=f"Coordinates consistent with Nominatim geocode within {threshold:.0f}m ({dist:.0f}m).",
            checked_at=now,
            evidence=evidence,
            limitations=["Consistency with OSM Nominatim only — not official AICTE map approval."],
        )

    return AdapterResult(
        adapter="geocode_nominatim",
        claim_type="coordinate_consistency",
        status=VerificationStatus.MANUAL_REVIEW_REQUIRED,
        source=VerificationSource.AUTHORIZED_LIVE,
        detail="Address geocoded; no extracted lat/lon to compare — officer should confirm map alignment.",
        checked_at=now,
        evidence=evidence,
        limitations=["Missing extracted coordinates"],
    )
