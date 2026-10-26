from __future__ import annotations

from collections.abc import Callable

from app.verification_engine.adapters.external_stubs import verify_authorized_stub
from app.verification_engine.adapters.geocode import verify_geocode
from app.verification_engine.adapters.pdf_signature import verify_pdf_signature
from app.verification_engine.adapters.types import AdapterContext, AdapterResult

AdapterFn = Callable[[AdapterContext], AdapterResult]


def _stub(adapter_id: str) -> AdapterFn:
    def _run(ctx: AdapterContext) -> AdapterResult:
        return verify_authorized_stub(adapter_id, ctx)

    return _run


_REGISTRY: dict[str, AdapterFn] = {
    "pdf_signature": verify_pdf_signature,
    "geocode_nominatim": verify_geocode,
    "aicte_payment": _stub("aicte_payment"),
    "building_permission": _stub("building_permission"),
    "fire_certificate": _stub("fire_certificate"),
    "engineer_credential": _stub("engineer_credential"),
    "auditor_credential": _stub("auditor_credential"),
}


def get_adapter(adapter_id: str) -> AdapterFn | None:
    return _REGISTRY.get(adapter_id)


def list_adapter_ids() -> list[str]:
    return sorted(_REGISTRY.keys())
