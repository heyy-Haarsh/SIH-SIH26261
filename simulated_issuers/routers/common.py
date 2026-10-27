from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from simulated_issuers.service import build_response


def make_verify_router(fixture_name: str, path: str) -> APIRouter:
    router = APIRouter()

    @router.post(path)
    async def verify(request: Request) -> dict[str, Any]:
        try:
            payload = await request.json()
        except Exception:
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        return build_response(fixture_name, payload)

    return router
