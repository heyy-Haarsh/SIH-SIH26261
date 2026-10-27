from __future__ import annotations

import os
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from datetime import datetime, timezone

from app.core import runtime_config
from app.core.config import settings
from app.models.enums import VerificationSource, VerificationStatus
from app.verification_engine.adapters.external_stubs import _ADAPTER_META, verify_authorized_stub
from app.verification_engine.adapters.geocode import verify_geocode
from app.verification_engine.adapters.http_connector_client import HTTPConnectorClient
from app.verification_engine.adapters.pdf_signature import verify_pdf_signature
from app.verification_engine.adapters.types import AdapterContext, AdapterResult

AdapterFn = Callable[[AdapterContext], AdapterResult]

_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "configs" / "connector_registry.yaml"

# Local / non-HTTP adapters always available
_LOCAL: dict[str, AdapterFn] = {
    "pdf_signature": verify_pdf_signature,
    "geocode_nominatim": verify_geocode,
}


def _default_base_url() -> str:
    return (settings.simulated_issuers_url or "http://127.0.0.1:8001").rstrip("/")


@lru_cache(maxsize=1)
def load_connector_registry() -> dict[str, Any]:
    raw = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    return raw.get("connectors") or {}


def clear_registry_cache() -> None:
    load_connector_registry.cache_clear()
    _http_clients.cache_clear()


@lru_cache(maxsize=32)
def _http_clients(adapter_id: str) -> HTTPConnectorClient | None:
    connectors = load_connector_registry()
    spec = connectors.get(adapter_id)
    if not spec:
        return None
    mode = str(spec.get("mode") or "simulated")
    if adapter_id in _LOCAL and mode == "real" and not spec.get("verify_path"):
        return None
    env_name = spec.get("base_url_env") or ""
    base = (os.getenv(env_name) if env_name else None) or _default_base_url()
    path = spec.get("verify_path") or ""
    if not path:
        return None
    return HTTPConnectorClient(
        connector_name=str(spec.get("connector_name") or adapter_id),
        base_url=base,
        verify_path=path,
        timeout=float(spec.get("timeout_seconds") or 10),
        retries=int(spec.get("retries") or 3),
        backoff_factor=float(spec.get("retry_backoff_factor") or 2),
        mode=mode,
        failure_threshold=int(spec.get("failure_threshold") or 3),
        cooldown_seconds=float(spec.get("cooldown_seconds") or 30),
    )


def _http_adapter(adapter_id: str) -> AdapterFn:
    def _run(ctx: AdapterContext) -> AdapterResult:
        if not settings.use_simulated_http_issuers:
            return verify_authorized_stub(adapter_id, ctx)
        client = _http_clients(adapter_id)
        if client is None:
            return verify_authorized_stub(adapter_id, ctx)
        return client.verify(ctx)

    return _run


def _admin_guard(adapter_id: str, fn: AdapterFn) -> AdapterFn:
    """Honour the administrator kill switch: a disabled integration never reports a result."""

    def _run(ctx: AdapterContext) -> AdapterResult:
        if runtime_config.integration_disabled_by_admin(adapter_id):
            reason = runtime_config.disabled_reason(adapter_id)
            claim = (
                "coordinate_consistency"
                if adapter_id == "geocode_nominatim"
                else "pdf_signature"
                if adapter_id == "pdf_signature"
                else _ADAPTER_META.get(adapter_id, {}).get("claim_type", "unknown")
            )
            return AdapterResult(
                adapter=adapter_id,
                claim_type=claim,
                status=VerificationStatus.SOURCE_UNAVAILABLE,
                source=VerificationSource.AUTHORIZED_LIVE,
                detail=(
                    "This verification source is switched off by an administrator"
                    + (f" ({reason})" if reason else "")
                    + ". No check was performed; manual review is required."
                ),
                checked_at=datetime.now(timezone.utc),
                limitations=["Integration disabled by administrator"],
                scope_of_confirmation="none — integration disabled",
            )
        return fn(ctx)

    return _run


def get_adapter(adapter_id: str) -> AdapterFn | None:
    if adapter_id in _LOCAL:
        return _admin_guard(adapter_id, _LOCAL[adapter_id])
    connectors = load_connector_registry()
    if adapter_id in connectors:
        return _admin_guard(adapter_id, _http_adapter(adapter_id))
    return None


def list_adapter_ids() -> list[str]:
    ids = set(_LOCAL.keys()) | set(load_connector_registry().keys())
    return sorted(ids)


def get_connector_spec(adapter_id: str) -> dict[str, Any] | None:
    return load_connector_registry().get(adapter_id)
