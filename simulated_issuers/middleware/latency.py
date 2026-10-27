from __future__ import annotations

import asyncio
import random
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from simulated_issuers.config import get_settings


class LatencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        delay_ms = settings.latency_ms
        if settings.latency_jitter_ms > 0:
            delay_ms += random.randint(0, settings.latency_jitter_ms)
        if delay_ms > 0:
            await asyncio.sleep(delay_ms / 1000.0)
        return await call_next(request)


def sync_sleep_if_needed() -> None:
    settings = get_settings()
    delay_ms = settings.latency_ms
    if settings.latency_jitter_ms > 0:
        delay_ms += random.randint(0, settings.latency_jitter_ms)
    if delay_ms > 0:
        time.sleep(delay_ms / 1000.0)
