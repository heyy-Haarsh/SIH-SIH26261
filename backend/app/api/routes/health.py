from fastapi import APIRouter

from app.core import runtime_config
from app.core.config import get_settings
from app.core.database import database_status
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    limitations = [
        "Demo header auth is for local SIH demos only — not production identity.",
        "External AICTE/municipal/fire/engineer/auditor connectors return SOURCE_UNAVAILABLE unless authorized.",
        "Layer 1 rule pass never establishes authenticity.",
        "Synthetic SYN-RULE-* rows are demo rules, not official AICTE handbook clauses.",
    ]
    if not settings.enable_nominatim_geocode:
        limitations.append("Nominatim geocoding disabled (ENABLE_NOMINATIM_GEOCODE=false).")
    if not settings.enable_live_verification:
        limitations.append("Live verification flag off — adapters stay unavailable/simulated.")
    return HealthResponse(
        status="ok",
        environment=settings.app_env,
        database=database_status(),
        storage_backend=settings.storage_backend,
        demo_auth=settings.demo_auth_enabled,
        app_version="0.1.0",
        max_upload_mb=runtime_config.max_upload_mb(),
        auto_extract_on_upload=runtime_config.auto_extract_on_upload(),
        enable_live_verification=settings.enable_live_verification,
        enable_nominatim_geocode=settings.enable_nominatim_geocode,
        limitations=limitations,
    )
