from fastapi import APIRouter

from app.core.config import get_settings
from app.core.database import database_status
from app.schemas.common import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        environment=settings.app_env,
        database=database_status(),
        storage_backend=settings.storage_backend,
        demo_auth=settings.demo_auth_enabled,
    )
