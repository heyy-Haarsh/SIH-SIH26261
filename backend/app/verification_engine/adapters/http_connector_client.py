"""HTTP connector client with tenacity retry + manual circuit breaker."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.models.enums import VerificationSource, VerificationStatus
from app.verification_engine.adapters.circuit_breaker import CircuitBreaker
from app.verification_engine.adapters.types import AdapterContext, AdapterResult

logger = logging.getLogger(__name__)

_STATUS_MAP = {
    "verified": VerificationStatus.SIMULATED_RESULT,
    "mismatch_detected": VerificationStatus.MISMATCH_DETECTED,
    "expired": VerificationStatus.EXPIRED,
    "verification_pending": VerificationStatus.VERIFICATION_PENDING,
    "source_unavailable": VerificationStatus.SOURCE_UNAVAILABLE,
    "manual_review_required": VerificationStatus.MANUAL_REVIEW_REQUIRED,
}

# adapter_id -> (path, preferred lookup fields)
ISSUER_ROUTES: dict[str, tuple[str, list[str]]] = {
    "fire_certificate": ("/issuers/fire-safety/verify", ["certificate_number", "reference_number"]),
    "building_permission": (
        "/issuers/building-occupancy/verify",
        ["certificate_number", "reference_number", "registration_number"],
    ),
    "engineer_credential": (
        "/issuers/structural-engineer/verify",
        ["engineer_registration_number", "membership_number", "registration_number"],
    ),
    "aicte_payment": ("/issuers/aicte-payment/verify", ["transaction_id", "receipt_number"]),
    "auditor_credential": (
        "/issuers/icai-membership/verify",
        ["auditor_registration_number", "membership_number", "ca_membership_number"],
    ),
    "affidavit_estamp": ("/issuers/affidavit-estamp/verify", ["stamp_paper_ref", "estamp_number"]),
}


def _is_retryable(exc: BaseException) -> bool:
    # Do not retry connection refused / DNS — fail fast to source_unavailable
    if isinstance(exc, (httpx.ConnectError, httpx.UnsupportedProtocol)):
        return False
    if isinstance(exc, httpx.TimeoutException):
        return True
    if isinstance(exc, httpx.TransportError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


class HTTPConnectorClient:
    def __init__(
        self,
        connector_name: str,
        base_url: str,
        *,
        verify_path: str,
        timeout: float = 10.0,
        retries: int = 3,
        backoff_factor: float = 2.0,
        mode: str = "simulated",
        failure_threshold: int = 3,
        cooldown_seconds: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.connector_name = connector_name
        self.base_url = base_url.rstrip("/")
        self.verify_path = verify_path
        self.timeout = timeout
        self.retries = max(1, retries)
        self.backoff_factor = backoff_factor
        self.mode = mode
        self.circuit = CircuitBreaker(
            failure_threshold=failure_threshold,
            cooldown_seconds=cooldown_seconds,
        )
        self._transport = transport

    def verify(self, ctx: AdapterContext) -> AdapterResult:
        now = datetime.now(timezone.utc)
        prefix = "[SIMULATED] " if self.mode == "simulated" else ""
        if not self.circuit.allow_request():
            return AdapterResult(
                adapter=self.connector_name,
                claim_type=self.connector_name,
                status=VerificationStatus.SOURCE_UNAVAILABLE,
                source=VerificationSource.SIMULATED_DEV
                if self.mode == "simulated"
                else VerificationSource.AUTHORIZED_LIVE,
                detail=f"{prefix}Circuit open — not calling {self.base_url}{self.verify_path}",
                checked_at=now,
                mode="SIMULATED" if self.mode == "simulated" else "REAL",
                official_verification=False,
                provider_name=self.connector_name,
                request_summary=f"skipped; circuit={self.circuit.state.value}",
                response_summary="circuit_open",
                scope_of_confirmation="none — circuit breaker open",
                limitations=["Circuit breaker open"],
            )

        try:
            data = self._call_with_retry(ctx.fields)
            self.circuit.record_success()
            return self._to_adapter_result(data, ctx, now)
        except httpx.TimeoutException:
            self.circuit.record_failure()
            return AdapterResult(
                adapter=self.connector_name,
                claim_type=self.connector_name,
                status=VerificationStatus.SOURCE_UNAVAILABLE,
                source=VerificationSource.SIMULATED_DEV
                if self.mode == "simulated"
                else VerificationSource.AUTHORIZED_LIVE,
                detail=f"{prefix}connector timeout",
                checked_at=now,
                mode="SIMULATED" if self.mode == "simulated" else "REAL",
                official_verification=False,
                provider_name=self.connector_name,
                request_summary=f"POST {self.verify_path}",
                response_summary="timeout",
                scope_of_confirmation="none — timeout",
                limitations=["Connector timeout"],
            )
        except Exception as exc:  # noqa: BLE001 — never crash pipeline
            self.circuit.record_failure()
            logger.warning("%sHTTP connector %s failed: %s", prefix, self.connector_name, exc)
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            reason = "service unavailable" if status_code == 503 else str(exc)[:200]
            return AdapterResult(
                adapter=self.connector_name,
                claim_type=self.connector_name,
                status=VerificationStatus.SOURCE_UNAVAILABLE,
                source=VerificationSource.SIMULATED_DEV
                if self.mode == "simulated"
                else VerificationSource.AUTHORIZED_LIVE,
                detail=f"{prefix}{reason}",
                checked_at=now,
                mode="SIMULATED" if self.mode == "simulated" else "REAL",
                official_verification=False,
                provider_name=self.connector_name,
                request_summary=f"POST {self.verify_path}",
                response_summary=reason,
                scope_of_confirmation="none — source unavailable",
                limitations=["HTTP connector error"],
                evidence={"error": reason},
            )

    def _call_with_retry(self, fields: dict[str, str]) -> dict[str, Any]:
        @retry(
            reraise=True,
            stop=stop_after_attempt(self.retries),
            wait=wait_exponential(multiplier=self.backoff_factor, min=0.05, max=2),
            retry=retry_if_exception(_is_retryable),
        )
        def _do() -> dict[str, Any]:
            # Short connect timeout so missing local issuer fails fast → source_unavailable
            timeout = httpx.Timeout(self.timeout, connect=min(0.25, self.timeout))
            with httpx.Client(transport=self._transport, timeout=timeout) as client:
                resp = client.post(
                    f"{self.base_url}{self.verify_path}",
                    json={"fields": fields},
                )
                if resp.status_code >= 500:
                    resp.raise_for_status()
                if resp.status_code >= 400:
                    # 4xx: do not retry
                    raise httpx.HTTPStatusError(
                        f"HTTP {resp.status_code}",
                        request=resp.request,
                        response=resp,
                    )
                return resp.json()

        return _do()

    def _to_adapter_result(
        self, data: dict[str, Any], ctx: AdapterContext, now: datetime
    ) -> AdapterResult:
        raw_status = str(data.get("status") or "source_unavailable")
        mapped = _STATUS_MAP.get(raw_status, VerificationStatus.SOURCE_UNAVAILABLE)
        # Simulated verified must never become verified_by_source
        if self.mode == "simulated" and raw_status == "verified":
            mapped = VerificationStatus.SIMULATED_RESULT
        mode = "SIMULATED" if self.mode == "simulated" or data.get("simulated") else "REAL"
        official = bool(data.get("official_verification", False)) and mode == "REAL"
        return AdapterResult(
            adapter=self.connector_name,
            claim_type=self.connector_name,
            status=mapped,
            source=VerificationSource.SIMULATED_DEV
            if mode == "SIMULATED"
            else VerificationSource.AUTHORIZED_LIVE,
            detail=str(data.get("detail") or data.get("response_summary") or raw_status),
            checked_at=now,
            mode=mode,  # type: ignore[arg-type]
            official_verification=official,
            provider_name=str(data.get("provider_name") or self.connector_name),
            provider_reference_id=data.get("provider_reference_id") or data.get("reference_id"),
            request_summary=str(data.get("request_summary") or f"fields={sorted(ctx.fields.keys())}"),
            response_summary=str(data.get("response_summary") or raw_status),
            scope_of_confirmation=str(
                data.get("scope_of_confirmation") or "fixture/registry lookup only"
            ),
            evidence={
                "matched_fields": data.get("matched_fields") or [],
                "mismatched_fields": data.get("mismatched_fields") or [],
                "raw_status": raw_status,
            },
            limitations=["SIMULATED result — not official verification"]
            if mode == "SIMULATED"
            else [],
        )
