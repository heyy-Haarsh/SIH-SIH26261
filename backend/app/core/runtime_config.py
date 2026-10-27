"""Administrator-adjustable runtime policy that sits *on top of* deployment configuration.

Deployment configuration (environment variables, ``.env``) decides what is possible and holds all
secrets. Administrators can only make things **stricter** at runtime:

- lower the maximum upload size and narrow the allowed file types,
- switch an integration off (kill switch) or back on — but never switch on an integration the
  deployment has not configured.

The values are persisted in ``system_settings`` and mirrored here so hot paths (adapters, upload
intake) do not need a database session. ``load_from_db`` is called on startup and after every
admin change.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings

_uploads: dict[str, Any] = {}
_integrations: dict[str, dict[str, Any]] = {}


def reset() -> None:
    _uploads.clear()
    _integrations.clear()


def apply(uploads: dict[str, Any] | None, integrations: dict[str, Any] | None) -> None:
    _uploads.clear()
    _uploads.update(uploads or {})
    _integrations.clear()
    for key, value in (integrations or {}).items():
        if isinstance(value, dict):
            _integrations[str(key)] = dict(value)


def load_from_db(db) -> None:
    """Refresh the in-process mirror from ``system_settings`` (missing rows → deployment defaults)."""
    from app.models.settings import SystemSetting

    rows = {
        r.key: (r.value or {})
        for r in db.query(SystemSetting).filter(SystemSetting.key.in_(("uploads", "integrations"))).all()
    }
    apply(rows.get("uploads"), (rows.get("integrations") or {}).get("overrides"))


# ---- uploads ----------------------------------------------------------------


def max_upload_bytes() -> int:
    cap = settings.max_upload_bytes
    try:
        configured = int(_uploads.get("maxUploadMb"))
    except (TypeError, ValueError):
        return cap
    if configured <= 0:
        return cap
    return min(cap, configured * 1024 * 1024)


def max_upload_mb() -> int:
    return max(1, max_upload_bytes() // (1024 * 1024))


def allowed_extensions() -> frozenset[str]:
    base = settings.allowed_extension_set
    raw = _uploads.get("allowedExtensions")
    if not isinstance(raw, list) or not raw:
        return base
    chosen = {str(e).strip().lower().lstrip(".") for e in raw if str(e).strip()}
    narrowed = frozenset(chosen & set(base))
    return narrowed or base


# ---- integrations -------------------------------------------------------------


def integration_override(integration_id: str) -> dict[str, Any]:
    return dict(_integrations.get(integration_id) or {})


def integration_disabled_by_admin(integration_id: str) -> bool:
    return _integrations.get(integration_id, {}).get("enabled") is False


def disabled_reason(integration_id: str) -> str:
    return str(_integrations.get(integration_id, {}).get("reason") or "")


def auto_extract_on_upload() -> bool:
    value = _uploads.get('autoExtractOnUpload')
    return value if isinstance(value, bool) else settings.auto_extract_on_upload

