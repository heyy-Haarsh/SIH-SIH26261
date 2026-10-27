"""Settings for the simulated issuer service."""

from __future__ import annotations

import os
from functools import lru_cache


class Settings:
    port: int
    host: str
    latency_ms: int
    latency_jitter_ms: int
    force_outage: bool
    random_5xx_rate: float
    rate_limit_rpm: int

    def __init__(self) -> None:
        self.host = os.getenv("SIMULATED_ISSUERS_HOST", "127.0.0.1")
        self.port = int(os.getenv("SIMULATED_ISSUERS_PORT", "8001"))
        self.latency_ms = int(os.getenv("SIMULATED_LATENCY_MS", "0"))
        self.latency_jitter_ms = int(os.getenv("SIMULATED_LATENCY_JITTER_MS", "0"))
        self.force_outage = os.getenv("FORCE_OUTAGE", "false").lower() in ("1", "true", "yes")
        self.random_5xx_rate = float(os.getenv("RANDOM_5XX_RATE", "0"))
        self.rate_limit_rpm = int(os.getenv("RATE_LIMIT_RPM", "120"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
