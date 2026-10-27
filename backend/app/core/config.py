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
    # ENABLE_AI_EXTRACTION only gates optional LLM-based extraction — never local PDF/OCR/deterministic fields.
    llm_api_key: str = ""
    llm_provider: str = "none"  # gemini | openai | none
    llm_model: str = ""
    # Sarvam speech-to-text (officer note dictation). Key stays on the server.
    sarvam_api_key: str = ""
    sarvam_stt_url: str = "https://api.sarvam.ai/speech-to-text"
    sarvam_stt_model: str = "saaras:v4"
    sarvam_realtime_ws_url: str = "wss://api.sarvam.ai/speech-to-text-realtime/ws"
    sarvam_realtime_model: str = "saaras:v3-realtime"
    enable_ai_extraction: bool = False
    aicte_api_base_url: str = ""
    aicte_api_key: str = ""
    enable_live_verification: bool = False

    # Phase 7 geocoding (public Nominatim) — off by default to respect usage limits
    enable_nominatim_geocode: bool = False
    nominatim_user_agent: str = "PRAMAN-SIH26261/0.1 (local-dev; contact=admin@praman.local)"
    geocode_mismatch_meters: float = 5000.0
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"

    # PDF PKI trust store (Phase 4) — empty by default; never ship CCA certs
    trust_store_dir: str = ""

    # Simulated issuer service (Phase 2)
    simulated_issuers_url: str = "http://127.0.0.1:8001"
    simulated_issuers_port: int = 8001
    # When false, Layer-2 authorized adapters use local stubs (no HTTP). Enable for real HTTP issuers.
    use_simulated_http_issuers: bool = False
    fire_issuer_base_url: str = ""
    building_issuer_base_url: str = ""
    structural_issuer_base_url: str = ""
    aicte_payment_issuer_base_url: str = ""
    icai_issuer_base_url: str = ""
    estamp_issuer_base_url: str = ""

    # Document intelligence (local; no cloud required)
    enable_local_pdf_extraction: bool = True
    enable_local_ocr: bool = True
    # Optional absolute path. Empty means PATH, then the default Windows install directory.
    tesseract_cmd: str = ""
    # Tesseract langs, "eng+hin+mar" or "eng,hin,mar". Marathi (mar) / Hindi (hin) need the
    # matching tessdata installed; missing packs degrade (English-only OCR) with a stated limitation.
    ocr_languages: str = "eng+hin+mar"
    ocr_dpi: int = 200
    max_extraction_pages: int = 50
    extraction_timeout_seconds: int = 120
    low_field_confidence_threshold: float = 0.55
    auto_extract_on_upload: bool = True

    # ---- derived helpers -------------------------------------------------
    @property
    def ocr_language_list(self) -> list[str]:
        raw = (self.ocr_languages or "").replace("+", ",")
        langs = [x.strip() for x in raw.split(",") if x.strip()]
        return langs or ["eng"]

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
