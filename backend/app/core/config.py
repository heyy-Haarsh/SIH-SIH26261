"""Application settings, loaded from environment variables / backend/.env.

Nothing in here contains secrets; real values come from the environment.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ directory (app/core/config.py -> parents[2])
BASE_DIR = Path(__file__).resolve().parents[2]


class ConfigurationError(RuntimeError):
    """Raised when the runtime configuration is unsafe or inconsistent."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # Application
    app_name: str = "PRAMAN"
    app_env: str = "development"
    debug: bool = False
    secret_key: str = "change-me-to-a-long-random-string"

    # Database
    database_url: str = "sqlite:///./praman_dev.db"
    use_sqlite_fallback: bool = False

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Demo auth (NOT secure - development only)
    demo_auth_enabled: bool = False

    # Uploads
    upload_dir: str = "./uploads"
    max_upload_mb: int = 25
    allowed_extensions: str = "pdf,png,jpg,jpeg,docx,txt"
    storage_backend: str = "local"

    # Async jobs (local sync runner is the only implemented runner)
    use_celery: bool = False
    redis_url: str = ""
    celery_broker_url: str = ""

    # AI / external verification (none are implemented as live integrations)
    llm_api_key: str = ""
    llm_provider: str = ""
    enable_ai_extraction: bool = False
    aicte_api_base_url: str = ""
    aicte_api_key: str = ""
    enable_live_verification: bool = False

    # ---- derived helpers -------------------------------------------------
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_extension_set(self) -> frozenset[str]:
        return frozenset(
            e.strip().lower().lstrip(".") for e in self.allowed_extensions.split(",") if e.strip()
        )

    @property
    def max_upload_bytes(self) -> int:
        return int(self.max_upload_mb) * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        if not p.is_absolute():
            p = BASE_DIR / p
        return p.resolve()

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() in {"production", "prod"}

    def validate_runtime(self) -> None:
        """Fail fast on unsafe configuration."""
        if self.is_production and self.demo_auth_enabled:
            raise ConfigurationError(
                "DEMO_AUTH_ENABLED must be false when APP_ENV=production. "
                "Demo header auth is not real authentication."
            )
        if self.is_production and self.secret_key.startswith("change-me"):
            raise ConfigurationError("SECRET_KEY must be set to a strong value in production.")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
