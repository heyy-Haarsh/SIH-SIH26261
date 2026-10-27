"""Phase 2: simulated issuer service, HTTP client, circuit breaker."""

from __future__ import annotations

import os
import socket
import sys
import time
from pathlib import Path

import httpx
import pytest
from starlette.testclient import TestClient

# Repo root on path for `simulated_issuers` package
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from simulated_issuers.config import clear_settings_cache
from simulated_issuers.main import app as issuers_app, assert_port_available
from simulated_issuers.service import clear_fixture_cache

from app.models.enums import VerificationStatus
from app.verification_engine.adapters.circuit_breaker import CircuitBreaker, CircuitState
from app.verification_engine.adapters.http_connector_client import HTTPConnectorClient
from app.verification_engine.adapters.registry import (
    clear_registry_cache,
    get_connector_spec,
    load_connector_registry,
    _http_clients,
)
from app.verification_engine.adapters.types import AdapterContext

STATUSES = [
    "verified",
    "mismatch_detected",
    "expired",
    "verification_pending",
    "source_unavailable",
    "manual_review_required",
]

CONNECTORS = [
    ("fire_safety", "/issuers/fire-safety/verify", "FIRE", "certificate_number"),
    ("building_occupancy", "/issuers/building-occupancy/verify", "BLD", "certificate_number"),
    ("structural_engineer", "/issuers/structural-engineer/verify", "ENG", "engineer_registration_number"),
    ("aicte_payment", "/issuers/aicte-payment/verify", "TXN", "transaction_id"),
    ("icai_membership", "/issuers/icai-membership/verify", "ICAI", "auditor_registration_number"),
    ("affidavit_estamp", "/issuers/affidavit-estamp/verify", "ESTAMP", "stamp_paper_ref"),
]

STATUS_KEY = {
    "verified": "VERIFIED",
    "mismatch_detected": "MISMATCH",
    "expired": "EXPIRED",
    "verification_pending": "PENDING",
    "source_unavailable": "UNAVAIL",
    "manual_review_required": "MANUAL",
}


def _issuer_transport() -> httpx.MockTransport:
    """Bridge sync httpx Client → Starlette TestClient (ASGITransport is async-only)."""
    st = TestClient(issuers_app)

    def handler(request: httpx.Request) -> httpx.Response:
        headers = {k: v for k, v in request.headers.items() if k.lower() != "host"}
        r = st.request(
            request.method,
            request.url.raw_path.decode("ascii"),
            content=request.content,
            headers=headers,
        )
        return httpx.Response(r.status_code, content=r.content, headers=r.headers)

    return httpx.MockTransport(handler)


@pytest.fixture
def issuer_client():
    clear_fixture_cache()
    clear_settings_cache()
    os.environ.pop("FORCE_OUTAGE", None)
    clear_settings_cache()
    return TestClient(issuers_app)


def _ctx(fields: dict) -> AdapterContext:
    return AdapterContext(
        document_id="d1",
        document_version_id="v1",
        requirement_code="FIRE_NOC",
        file_path=None,
        mime_type="application/pdf",
        fields=fields,
    )


@pytest.mark.parametrize("fixture_name,path,prefix,field", CONNECTORS)
@pytest.mark.parametrize("status", STATUSES)
def test_a_all_statuses_reachable(issuer_client, fixture_name, path, prefix, field, status):
    key = f"{prefix}-{STATUS_KEY[status]}-001"
    res = issuer_client.post(path, json={"fields": {field: key}})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == status
    assert body["simulated"] is True
    assert body["official_verification"] is False
    assert body["mode"] == "SIMULATED"


def test_b_verified_never_official(issuer_client):
    res = issuer_client.post(
        "/issuers/fire-safety/verify",
        json={"fields": {"certificate_number": "FIRE-VERIFIED-001"}},
    )
    body = res.json()
    assert body["status"] == "verified"
    assert body["official_verification"] is False
    assert body["simulated"] is True


def test_c_force_outage_503(monkeypatch):
    monkeypatch.setenv("FORCE_OUTAGE", "true")
    clear_settings_cache()
    client = TestClient(issuers_app)
    res = client.post(
        "/issuers/fire-safety/verify",
        json={"fields": {"certificate_number": "FIRE-VERIFIED-001"}},
    )
    assert res.status_code == 503
    body = res.json()
    assert body["status"] == "source_unavailable"
    assert body["official_verification"] is False
    monkeypatch.delenv("FORCE_OUTAGE", raising=False)
    clear_settings_cache()


def test_http_client_outage_to_source_unavailable(monkeypatch):
    monkeypatch.setenv("FORCE_OUTAGE", "true")
    clear_settings_cache()
    client = HTTPConnectorClient(
        "fire",
        "http://test",
        verify_path="/issuers/fire-safety/verify",
        retries=1,
        transport=_issuer_transport(),
        mode="simulated",
    )
    result = client.verify(_ctx({"certificate_number": "FIRE-VERIFIED-001"}))
    assert result.status == VerificationStatus.SOURCE_UNAVAILABLE
    monkeypatch.delenv("FORCE_OUTAGE", raising=False)
    clear_settings_cache()


def test_http_client_timeout_source_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("slow", request=request)

    transport = httpx.MockTransport(handler)
    client = HTTPConnectorClient(
        "fire",
        "http://test",
        verify_path="/issuers/fire-safety/verify",
        retries=1,
        timeout=0.1,
        transport=transport,
        mode="simulated",
    )
    result = client.verify(_ctx({"certificate_number": "x"}))
    assert result.status == VerificationStatus.SOURCE_UNAVAILABLE
    assert "timeout" in result.detail.lower() or result.response_summary == "timeout"


def test_circuit_breaker_state_transitions():
    cb = CircuitBreaker(failure_threshold=2, cooldown_seconds=0.2)
    assert cb.state == CircuitState.CLOSED
    assert cb.allow_request() is True
    cb.record_failure()
    assert cb.state == CircuitState.CLOSED
    cb.record_failure()
    assert cb.state == CircuitState.OPEN
    assert cb.allow_request() is False
    time.sleep(0.25)
    assert cb.state == CircuitState.HALF_OPEN
    assert cb.allow_request() is True
    cb.record_success()
    assert cb.state == CircuitState.CLOSED


def test_circuit_open_returns_source_unavailable_no_crash():
    client = HTTPConnectorClient(
        "fire",
        "http://test",
        verify_path="/issuers/fire-safety/verify",
        retries=1,
        failure_threshold=1,
        cooldown_seconds=60,
        transport=_issuer_transport(),
        mode="simulated",
    )
    client.circuit.record_failure()
    assert client.circuit.state == CircuitState.OPEN
    result = client.verify(_ctx({"certificate_number": "FIRE-VERIFIED-001"}))
    assert result.status == VerificationStatus.SOURCE_UNAVAILABLE
    assert "circuit" in result.detail.lower()


def test_busy_port_fails_loudly():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.listen(1)
    try:
        with pytest.raises(SystemExit) as ei:
            assert_port_available("127.0.0.1", port)
        msg = str(ei.value)
        assert "already in use" in msg.lower() or "SIMULATED_ISSUERS_PORT" in msg
    finally:
        sock.close()


def test_registry_yaml_loads_and_mode_switch(monkeypatch):
    clear_registry_cache()
    specs = load_connector_registry()
    assert "fire_certificate" in specs
    assert specs["fire_certificate"]["mode"] == "simulated"
    fire = get_connector_spec("fire_certificate")
    assert fire is not None
    monkeypatch.setenv("FIRE_ISSUER_BASE_URL", "http://example.invalid:9999")
    clear_registry_cache()
    client = _http_clients("fire_certificate")
    assert client is not None
    assert client.base_url == "http://example.invalid:9999"
    clear_registry_cache()


def test_simulated_verified_maps_to_simulated_result():
    client = HTTPConnectorClient(
        "fire_certificate",
        "http://test",
        verify_path="/issuers/fire-safety/verify",
        retries=1,
        transport=_issuer_transport(),
        mode="simulated",
    )
    result = client.verify(_ctx({"certificate_number": "FIRE-VERIFIED-001"}))
    assert result.official_verification is False
    assert result.mode == "SIMULATED"
    assert result.status == VerificationStatus.SIMULATED_RESULT
