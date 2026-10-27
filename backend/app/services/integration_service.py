"""Integration catalogue, configuration state and health for the administrator.

Principles
- Report what is true. An integration that is not configured says so; a simulated connector is
  labelled simulated; "configured" never implies "verified live" unless a probe actually succeeded.
- Secrets never leave the process. Only booleans such as ``credentialsConfigured`` are exposed.
- Deployment configuration decides what is *possible*. The administrator may switch an integration
  off (kill switch) or back on, but cannot enable something the deployment has not configured.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core import runtime_config
from app.core.config import settings
from app.core.database import DB_MODE, engine
from app.core.errors import NotFoundError, UnprocessableError
from app.models.settings import SystemSetting
from app.models.user import User
from app.services.audit_service import record_audit

SETTING_KEY = "integrations"

# health values
HEALTHY = "healthy"
DEGRADED = "degraded"
UNAVAILABLE = "unavailable"
NOT_CONFIGURED = "not_configured"
DISABLED = "disabled"
SIMULATED = "simulated"

_ISSUER_META: dict[str, tuple[str, str]] = {
    "aicte_payment": ("AICTE payment receipt registry", "Confirms AICTE fee payment receipts with the issuer."),
    "building_permission": ("Building permission / occupancy authority", "Confirms occupancy and building permissions."),
    "fire_certificate": ("Fire safety certificate authority", "Confirms fire safety certificates with the fire service."),
    "engineer_credential": ("Structural engineer credential registry", "Confirms structural engineer registration."),
    "auditor_credential": ("Auditor / CA membership registry", "Confirms auditor membership with the professional body."),
    "affidavit_estamp": ("Affidavit e-stamp registry", "Confirms e-stamp details on affidavits."),
}

_LAST_PROBE: dict[str, dict[str, Any]] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _entry(
    integration_id: str,
    label: str,
    category: str,
    description: str,
    *,
    health: str,
    mode: str,
    message: str,
    configured: bool,
    deployment_enabled: bool = True,
    requires_credentials: bool = False,
    credentials_configured: bool | None = None,
    details: dict[str, Any] | None = None,
    limitations: list[str] | None = None,
    can_toggle: bool = True,
    probed: bool = False,
) -> dict[str, Any]:
    override = runtime_config.integration_override(integration_id)
    admin_enabled = override.get("enabled") is not False
    effective = bool(configured and deployment_enabled and admin_enabled)
    shown_health = health
    shown_message = message
    if not admin_enabled:
        shown_health = DISABLED
        shown_message = "Switched off by an administrator." + (
            f" Reason: {override.get('reason')}" if override.get("reason") else ""
        )
    last = _LAST_PROBE.get(integration_id)
    return {
        "id": integration_id,
        "label": label,
        "category": category,
        "description": description,
        "health": shown_health,
        "mode": mode,
        "message": shown_message,
        "configured": configured,
        "deploymentEnabled": deployment_enabled,
        "adminEnabled": admin_enabled,
        "effectiveEnabled": effective,
        "requiresCredentials": requires_credentials,
        "credentialsConfigured": credentials_configured,
        "details": details or {},
        "limitations": limitations or [],
        "canToggle": can_toggle,
        "adminReason": override.get("reason") or "",
        "adminChangedBy": override.get("updatedBy") or "",
        "adminChangedAt": override.get("updatedAt") or None,
        "lastCheck": last,
        "probed": probed or bool(last),
    }


# ---- individual probes -----------------------------------------------------------


def _database() -> dict[str, Any]:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ok = True
    except Exception as exc:  # noqa: BLE001
        ok = False
        err = exc.__class__.__name__
    sqlite = DB_MODE != "postgresql"
    if not ok:
        return _entry(
            "database", "Database", "infrastructure", "Primary application database.",
            health=UNAVAILABLE, mode="real", message=f"Database connection failed ({err}).",
            configured=True, can_toggle=False, probed=True,
        )
    health = DEGRADED if (sqlite and settings.is_production) else HEALTHY
    msg = "Connected."
    if sqlite:
        msg = "Connected to SQLite (development fallback)." + (
            " SQLite is not suitable for production." if settings.is_production else ""
        )
    return _entry(
        "database", "Database", "infrastructure", "Primary application database.",
        health=health, mode="real", message=msg, configured=True, can_toggle=False, probed=True,
        details={"engine": "postgresql" if not sqlite else "sqlite"},
    )


def _storage() -> dict[str, Any]:
    path = settings.upload_path
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path, prefix=".health-", delete=True):
            pass
        free_mb = int(shutil.disk_usage(path).free / (1024 * 1024))
    except Exception as exc:  # noqa: BLE001
        return _entry(
            "file_storage", "Document storage", "infrastructure", "Where uploaded documents are kept.",
            health=UNAVAILABLE, mode="local", message=f"Upload folder is not writable ({exc.__class__.__name__}).",
            configured=True, can_toggle=False, probed=True,
            details={"backend": settings.storage_backend},
        )
    health = DEGRADED if free_mb < 500 else HEALTHY
    msg = "Upload folder is writable." if health == HEALTHY else f"Only {free_mb} MB of disk space is free."
    return _entry(
        "file_storage", "Document storage", "infrastructure", "Where uploaded documents are kept.",
        health=health, mode="local", message=msg, configured=True, can_toggle=False, probed=True,
        details={"backend": settings.storage_backend, "freeDiskMb": free_mb},
        limitations=["Local filesystem storage only; object storage (MinIO/S3) is not implemented."]
        if settings.storage_backend == "local"
        else [],
    )


def _pdf_extraction() -> dict[str, Any]:
    if not settings.enable_local_pdf_extraction:
        return _entry(
            "pdf_extraction", "PDF text extraction", "document_processing",
            "Reads embedded text from PDFs.", health=DISABLED, mode="local",
            message="Disabled by deployment configuration.", configured=True, deployment_enabled=False,
        )
    try:
        import fitz  # noqa: F401  # PyMuPDF

        engine_name = "PyMuPDF"
    except Exception:  # noqa: BLE001
        engine_name = ""
    if not engine_name:
        return _entry(
            "pdf_extraction", "PDF text extraction", "document_processing",
            "Reads embedded text from PDFs.", health=UNAVAILABLE, mode="local",
            message="No PDF library is installed.", configured=True,
        )
    return _entry(
        "pdf_extraction", "PDF text extraction", "document_processing",
        "Reads embedded text from PDFs.", health=HEALTHY, mode="local",
        message="Available.", configured=True, details={"library": engine_name},
    )


def _ocr() -> dict[str, Any]:
    from app.document_processing.ocr_processor import tesseract_status

    st = tesseract_status()
    wanted = st.get("languages_requested") or []
    missing = st.get("languages_missing") or []
    details = {
        "tesseractVersion": st.get("tesseract_version"),
        "languagesRequested": wanted,
        "languagesUsable": st.get("languages_usable") or [],
        "languagesMissing": missing,
        "marathiSupported": bool(st.get("marathi_supported")),
    }
    if not st.get("enabled"):
        return _entry(
            "ocr", "OCR (Tesseract)", "document_processing", "Reads scanned documents and images.",
            health=DISABLED, mode="local", message=st.get("message") or "Disabled.", configured=True,
            deployment_enabled=False, details=details,
        )
    if not st.get("available"):
        return _entry(
            "ocr", "OCR (Tesseract)", "document_processing", "Reads scanned documents and images.",
            health=UNAVAILABLE, mode="local", message=st.get("message") or "Not available.",
            configured=True, details=details,
            limitations=["Scanned and photographed documents cannot be read until OCR is installed."],
        )
    limitations = []
    if "mar" in wanted and not st.get("marathi_supported"):
        limitations.append("Marathi affidavits cannot be read: the Marathi (mar) language data is not installed.")
    return _entry(
        "ocr", "OCR (Tesseract)", "document_processing", "Reads scanned documents and images.",
        health=DEGRADED if missing else HEALTHY, mode="local", message=st.get("message") or "Ready.",
        configured=True, details=details, limitations=limitations,
    )


def _llm() -> dict[str, Any]:
    provider = (settings.llm_provider or "none").lower()
    key = bool((settings.llm_api_key or "").strip())
    details = {"provider": provider, "model": settings.llm_model or None}
    desc = "Optional AI-assisted field extraction. Never used to decide an application."
    if not settings.enable_ai_extraction:
        return _entry(
            "llm_extraction", "AI extraction (LLM)", "ai", desc, health=DISABLED, mode="off",
            message="Disabled — deterministic extraction only.", configured=False,
            deployment_enabled=False, requires_credentials=True, credentials_configured=key, details=details,
        )
    if provider == "none" or not key:
        return _entry(
            "llm_extraction", "AI extraction (LLM)", "ai", desc, health=NOT_CONFIGURED, mode="off",
            message="Enabled but no provider/API key is configured.", configured=False,
            requires_credentials=True, credentials_configured=key, details=details,
        )
    return _entry(
        "llm_extraction", "AI extraction (LLM)", "ai", desc, health=HEALTHY, mode="real",
        message="Configured. Not live-tested by this page.", configured=True,
        requires_credentials=True, credentials_configured=True, details=details,
        limitations=["Credentials are present; connectivity is not probed to avoid usage cost."],
    )


def _geocode() -> dict[str, Any]:
    host = urlparse(settings.nominatim_base_url).netloc
    desc = "Checks stated coordinates against the address using public OpenStreetMap Nominatim."
    if not settings.enable_nominatim_geocode:
        return _entry(
            "geocode_nominatim", "Geocoding (Nominatim)", "verification", desc, health=DISABLED,
            mode="real", message="Off (ENABLE_NOMINATIM_GEOCODE=false) to respect public usage limits.",
            configured=True, deployment_enabled=False, details={"host": host},
        )
    return _entry(
        "geocode_nominatim", "Geocoding (Nominatim)", "verification", desc, health=HEALTHY, mode="real",
        message="Enabled. Public service, rate-limited to one request per second; not probed here.",
        configured=True, details={"host": host},
    )


def _pdf_signature() -> dict[str, Any]:
    desc = "Checks PDF digital signatures and whether a file changed after signing."
    try:
        import pyhanko  # noqa: F401

        lib = True
    except Exception:  # noqa: BLE001
        lib = False
    trust = (settings.trust_store_dir or "").strip()
    trust_ok = bool(trust and os.path.isdir(trust))
    details = {"pyhankoInstalled": lib, "trustStoreConfigured": trust_ok}
    if not lib:
        return _entry(
            "pdf_signature", "PDF signature checks", "verification", desc, health=DEGRADED, mode="local",
            message="Signature library not installed; only basic signature flags can be read.",
            configured=True, details=details,
        )
    if not trust_ok:
        return _entry(
            "pdf_signature", "PDF signature checks", "verification", desc, health=DEGRADED, mode="local",
            message="Integrity checks work; certificate chains cannot be trusted without a trust store.",
            configured=True, details=details,
            limitations=["No trust store: a valid signature is reported as untrusted, never as verified."],
        )
    return _entry(
        "pdf_signature", "PDF signature checks", "verification", desc, health=HEALTHY, mode="local",
        message="Ready with a configured trust store.", configured=True, details=details,
    )


def _issuer_base(adapter_id: str, spec: dict[str, Any]) -> str:
    env_name = spec.get("base_url_env") or ""
    val = (os.getenv(env_name) if env_name else None) or (getattr(settings, env_name.lower(), "") if env_name else "")
    return (val or settings.simulated_issuers_url or "").rstrip("/")


def _issuers() -> list[dict[str, Any]]:
    from app.verification_engine.adapters import registry

    out: list[dict[str, Any]] = []
    specs = registry.load_connector_registry()
    for adapter_id, (label, desc) in _ISSUER_META.items():
        spec = specs.get(adapter_id) or {}
        base = _issuer_base(adapter_id, spec)
        http = settings.use_simulated_http_issuers
        details: dict[str, Any] = {
            "connector": spec.get("connector_name"),
            "registryMode": spec.get("mode"),
            "timeoutSeconds": spec.get("timeout_seconds"),
            "retries": spec.get("retries"),
        }
        limitations = ["Even when reachable, a simulated issuer is never an official verification."]
        if http:
            details["host"] = urlparse(base).netloc
            client = registry._http_clients(adapter_id)
            if client is not None:
                details["circuitBreaker"] = client.circuit.state.value
            health = SIMULATED
            msg = "Using the simulated issuer service. Results are labelled simulated and are never official."
            if client is not None and details.get("circuitBreaker") == "open":
                health = DEGRADED
                msg = "Simulated issuer service is failing — circuit breaker is open."
            out.append(_entry(
                adapter_id, label, "verification", desc, health=health, mode="simulated", message=msg,
                configured=True, requires_credentials=True, credentials_configured=False,
                details=details, limitations=limitations,
            ))
        else:
            msg = "No authorized connector is configured. Checks report 'source unavailable' and need manual review."
            if settings.enable_live_verification:
                msg = "Live verification is switched on but no connector for this source is implemented in this build."
            out.append(_entry(
                adapter_id, label, "verification", desc, health=NOT_CONFIGURED, mode="off", message=msg,
                configured=False, requires_credentials=True, credentials_configured=False,
                details=details, limitations=["Requires authorized access from the issuing authority."],
            ))
    return out


def _aicte() -> dict[str, Any]:
    base = bool((settings.aicte_api_base_url or "").strip())
    key = bool((settings.aicte_api_key or "").strip())
    desc = "Institutional records from AICTE."
    details = {"baseUrlConfigured": base}
    if base and key:
        return _entry(
            "aicte_api", "AICTE institutional API", "verification", desc, health=DEGRADED, mode="off",
            message="Credentials are present, but no AICTE connector is implemented in this build.",
            configured=False, requires_credentials=True, credentials_configured=True, details=details,
        )
    return _entry(
        "aicte_api", "AICTE institutional API", "verification", desc, health=NOT_CONFIGURED, mode="off",
        message="No authorized AICTE access is configured.", configured=False,
        requires_credentials=True, credentials_configured=key, details=details,
        limitations=["Institution-level facts are never claimed as AICTE-verified."],
    )


def _jobs() -> dict[str, Any]:
    desc = "Runs extraction and validation."
    if settings.use_celery:
        return _entry(
            "job_runner", "Background job runner", "infrastructure", desc, health=DEGRADED, mode="local",
            message="Celery is switched on but only the in-process runner is implemented; jobs still run inline.",
            configured=True, can_toggle=False, details={"runner": "local_sync", "celeryRequested": True},
        )
    return _entry(
        "job_runner", "Background job runner", "infrastructure", desc, health=HEALTHY, mode="local",
        message="In-process runner; extraction and validation run synchronously.", configured=True,
        can_toggle=False, details={"runner": "local_sync"},
    )


def list_integrations() -> list[dict[str, Any]]:
    items = [
        _database(), _storage(), _jobs(), _pdf_extraction(), _ocr(), _llm(), _geocode(),
        _pdf_signature(), *_issuers(), _aicte(),
    ]
    return items


def get_integration(integration_id: str) -> dict[str, Any]:
    for item in list_integrations():
        if item["id"] == integration_id:
            return item
    raise NotFoundError(f"Unknown integration: {integration_id}")


# ---- active probes ---------------------------------------------------------------


def check_integration(integration_id: str) -> dict[str, Any]:
    """Run a live probe where one is safe; record the outcome as the last check."""
    item = get_integration(integration_id)
    outcome: dict[str, Any] = {"checkedAt": _now().isoformat(), "ok": None, "message": ""}
    if integration_id in _ISSUER_META:
        if not settings.use_simulated_http_issuers:
            outcome.update(ok=False, message="No connector is configured; nothing to probe.")
        else:
            from app.verification_engine.adapters import registry

            spec = registry.load_connector_registry().get(integration_id) or {}
            base = _issuer_base(integration_id, spec)
            try:
                import httpx

                with httpx.Client(timeout=1.5) as client:
                    resp = client.get(f"{base}/health")
                outcome.update(ok=resp.status_code < 500, message=f"Simulated issuer service answered HTTP {resp.status_code}.")
            except Exception as exc:  # noqa: BLE001
                outcome.update(ok=False, message=f"Simulated issuer service unreachable ({exc.__class__.__name__}).")
    elif integration_id in {"database", "file_storage", "ocr", "pdf_extraction", "pdf_signature", "job_runner"}:
        ok = item["health"] in (HEALTHY, DEGRADED)
        outcome.update(ok=ok, message=item["message"])
    else:
        outcome.update(
            ok=None,
            message="No safe live probe for this integration (it would call a paid or rate-limited external service).",
        )
    _LAST_PROBE[integration_id] = outcome
    return get_integration(integration_id)


# ---- admin configuration -----------------------------------------------------------


def _row(db: Session) -> SystemSetting:
    row = db.query(SystemSetting).filter(SystemSetting.key == SETTING_KEY).first()
    if row is None:
        row = SystemSetting(
            key=SETTING_KEY, value={"overrides": {}},
            description="Administrator switches for integrations (no secrets).", change_reason="default",
        )
        db.add(row)
        db.flush()
    return row


def set_integration_enabled(
    db: Session, actor: User, integration_id: str, *, enabled: bool, reason: str
) -> dict[str, Any]:
    item = get_integration(integration_id)
    if not item["canToggle"]:
        raise UnprocessableError(f"{item['label']} is core infrastructure and cannot be switched off here.")
    reason = (reason or "").strip()
    if len(reason) < 3:
        raise UnprocessableError("A reason (at least 3 characters) is required.")
    row = _row(db)
    current = dict((row.value or {}).get("overrides") or {})
    before = current.get(integration_id, {}).get("enabled", True)
    if enabled:
        # Switching back on only removes the kill switch; it can never make an unconfigured
        # integration live (credentials and endpoints live in the server configuration).
        current.pop(integration_id, None)
    else:
        current[integration_id] = {
            "enabled": False,
            "reason": reason,
            "updatedBy": actor.name,
            "updatedAt": _now().isoformat(),
        }
    row.value = {"overrides": current}
    row.updated_by_id = actor.id
    row.change_reason = reason
    record_audit(
        db,
        action="admin.integration_toggled",
        actor=actor.name,
        actor_id=actor.id,
        actor_role=actor.role.value,
        detail=f"{integration_id}: {'enabled' if enabled else 'disabled'}; reason={reason}",
        entity_type="integration",
        metadata={"integration": integration_id, "before": {"enabled": before}, "after": {"enabled": enabled}, "reason": reason},
    )
    db.commit()
    runtime_config.load_from_db(db)
    return get_integration(integration_id)


def summarize(items: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items:
        out[it["health"]] = out.get(it["health"], 0) + 1
    return out
