"""Read-only view of background processing work.

There is no separate job table on purpose: every validation and extraction run already records
its own status, timing and error, so this module only presents those records in one list. That
keeps the job view from drifting away from what actually ran.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.extraction import ExtractionRun
from app.models.validation import ValidationRun

# Plain-language outcome buckets, so the UI does not need to know each run type's status names.
_FAILED = {"failed"}
_ATTENTION = {"requires_ocr", "ocr_unavailable", "unsupported", "requires_manual_review", "completed_with_warnings"}
_ACTIVE = {"queued", "running"}


def _bucket(status: str) -> str:
    if status in _FAILED:
        return "failed"
    if status in _ATTENTION:
        return "needs_attention"
    if status in _ACTIVE:
        return "active"
    return "ok"


def _seconds(started, completed) -> Optional[float]:
    if started and completed:
        return round((completed - started).total_seconds(), 2)
    return None


def list_jobs(
    db: Session,
    *,
    kind: Optional[str] = None,
    outcome: Optional[str] = None,
    limit: int = 100,
) -> dict[str, Any]:
    """Most recent runs first. ``outcome`` is one of ok / active / failed / needs_attention."""
    limit = max(1, min(limit, 500))
    numbers = {a.id: a.application_number for a in db.query(Application.id, Application.application_number)}
    items: list[dict[str, Any]] = []

    if kind in (None, "validation"):
        for r in db.query(ValidationRun).order_by(ValidationRun.created_at.desc()).limit(limit):
            status = r.status.value
            items.append(
                {
                    "id": r.id,
                    "kind": "validation",
                    "applicationId": r.application_id,
                    "applicationNumber": numbers.get(r.application_id),
                    "status": status,
                    "outcome": _bucket(status),
                    "trigger": r.trigger,
                    "createdAt": r.created_at,
                    "startedAt": r.started_at,
                    "completedAt": r.completed_at,
                    "durationSeconds": _seconds(r.started_at, r.completed_at),
                    "error": r.error_message,
                    "detail": f"rule set {r.rule_set_version or 'n/a'}",
                }
            )
    if kind in (None, "extraction"):
        for r in db.query(ExtractionRun).order_by(ExtractionRun.created_at.desc()).limit(limit):
            status = r.status.value
            items.append(
                {
                    "id": r.id,
                    "kind": "extraction",
                    "applicationId": r.application_id,
                    "applicationNumber": numbers.get(r.application_id),
                    "status": status,
                    "outcome": _bucket(status),
                    "trigger": None,
                    "createdAt": r.created_at,
                    "startedAt": r.started_at,
                    "completedAt": r.completed_at,
                    "durationSeconds": _seconds(r.started_at, r.completed_at),
                    "error": r.error_message or r.error_code,
                    "detail": None,
                }
            )

    if outcome:
        items = [i for i in items if i["outcome"] == outcome]
    items.sort(key=lambda i: i["createdAt"], reverse=True)
    items = items[:limit]
    counts = {"ok": 0, "active": 0, "failed": 0, "needs_attention": 0}
    for i in items:
        counts[i["outcome"]] += 1
    return {
        "items": items,
        "counts": counts,
        # Honest execution mode: there is no worker queue; runs execute inside the request.
        "executionMode": "synchronous",
        "message": (
            "Validation and extraction run synchronously inside the request that triggers them. "
            "There is no background worker queue. A run still marked 'running' long after it "
            "started means the request was interrupted and the run should be repeated."
        ),
    }
