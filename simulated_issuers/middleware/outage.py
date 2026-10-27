from __future__ import annotations

import random

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from simulated_issuers.config import get_settings


class OutageMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        settings = get_settings()
        if settings.force_outage:
            return JSONResponse(
                status_code=503,
                content={
                    "simulated": True,
                    "status": "source_unavailable",
                    "detail": "[SIMULATED] Forced outage (FORCE_OUTAGE=true)",
                    "mode": "SIMULATED",
                    "official_verification": False,
                },
            )
        if settings.random_5xx_rate > 0 and random.random() < settings.random_5xx_rate:
            code = random.choice([500, 502, 503])
            return JSONResponse(
                status_code=code,
                content={
                    "simulated": True,
                    "status": "source_unavailable",
                    "detail": f"[SIMULATED] Injected {code}",
                    "mode": "SIMULATED",
                    "official_verification": False,
                },
            )
        return await call_next(request)
