"""System-health roll-up for the administrator: infrastructure, pipeline services, recent activity."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.application import Application
from app.models.audit import AuditEvent
from app.models.doc_verification import DocumentVerificationCheck
from app.models.enums import ExtractionRunStatus, ValidationRunStatus
from app.models.extraction import ExtractionRun
from app.models.rule import RegulatoryRule
from app.models.validation import ValidationRun
from app.services import integration_service as isvc
from app.services.audit_chain_service import verify_chain_integrity

# Components whose failure makes the whole system unhealthy / degraded.
_CORE = {"database", "file_storage"}
_PIPELINE = {"pdf_extraction", "ocr", "pdf_signature", "job_runner"}
_WATCHED = _CORE | _PIPELINE | {"audit_chain"}


def _since(hours: int) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=hours)


def _component(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item["id"],
        "label": item["label"],
        "category": item["category"],
        "health": item["health"],
        "message": item["message"],
        "limitations": item["limitations"],
    }


def _audit_chain(db: Session) -> dict[str, Any]:
    result = verify_chain_integrity(db)
    return {
        "id": "audit_chain",
        "label": "Tamper-evident audit chain",
        "category": "infrastructure",
        "health": isvc.HEALTHY if result.ok else isvc.UNAVAILABLE,
        "message": (
            f"{result.checked} chained event(s) verified."
            if result.ok
            else f"Chain broken at sequence {result.first_bad_sequence}: {result.detail}."
        ),
        "limitations": [],
    }


def _rule_engine(db: Session) -> dict[str, Any]:
    rules = db.query(RegulatoryRule).all()
    active = sum(1 for r in rules if r.is_active)
    drafts = sum(1 for r in rules for v in r.versions if (v.status or "") == "draft")
    return {
        "id": "rule_engine",
        "label": "Rule engine",
        "category": "pipeline",
        "health": isvc.HEALTHY,
        "message": f"{active} of {len(rules)} rule(s) active; {drafts} draft version(s) awaiting review.",
        "limitations": ["Rules shipped with the demo are synthetic and are not official AICTE rules."],
    }


def _activity(db: Session) -> dict[str, Any]:
    since = _since(24)
    status_counts = {
        str(getattr(s, "value", s)): n
        for s, n in db.query(Application.status, func.count(Application.id)).group_by(Application.status).all()
    }
    runs = db.query(ValidationRun).filter(ValidationRun.created_at >= since)
    vr_total = runs.count()
    vr_failed = runs.filter(ValidationRun.status == ValidationRunStatus.FAILED).count()
    ex = db.query(ExtractionRun).filter(ExtractionRun.created_at >= since)
    needs_attention = [
        ExtractionRunStatus.FAILED,
        ExtractionRunStatus.OCR_UNAVAILABLE,
        ExtractionRunStatus.REQUIRES_OCR,
        ExtractionRunStatus.UNSUPPORTED,
    ]
    unavailable_checks = (
        db.query(DocumentVerificationCheck)
        .filter(DocumentVerificationCheck.created_at >= since)
        .filter(DocumentVerificationCheck.outcome == "source_unavailable")
        .count()
    )
    return {
        "windowHours": 24,
        "applicationsByStatus": status_counts,
        "applicationsTotal": sum(status_counts.values()),
        "validationRuns": vr_total,
        "validationRunsFailed": vr_failed,
        "extractionRuns": ex.count(),
        "extractionRunsFailed": ex.filter(ExtractionRun.status == ExtractionRunStatus.FAILED).count(),
        "extractionRunsNeedingAttention": ex.filter(ExtractionRun.status.in_(needs_attention)).count(),
        "verificationChecksUnavailable": unavailable_checks,
        "lastAuditEventAt": db.query(func.max(AuditEvent.created_at)).scalar(),
        "lastValidationAt": db.query(func.max(ValidationRun.created_at)).scalar(),
        "auditEvents": db.query(AuditEvent).filter(AuditEvent.created_at >= since).count(),
    }


def _warnings(items: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    if settings.demo_auth_enabled:
        out.append("Demo header authentication is on. It is for local demos only and is not real identity.")
    if settings.secret_key.startswith("change-me"):
        out.append("SECRET_KEY still has its placeholder value.")
    for it in items:
        if it["id"] in ("ocr", "database") and it["health"] in (isvc.UNAVAILABLE, isvc.DEGRADED):
            out.append(f"{it['label']}: {it['message']}")
    unconnected = [i for i in items if i["id"] in isvc._ISSUER_META and i["health"] == isvc.NOT_CONFIGURED]
    if unconnected:
        out.append(
            f"{len(unconnected)} official verification source(s) are not connected, so those checks always "
            "need manual review."
        )
    return out


def overall_status(components: list[dict[str, Any]]) -> str:
    by_id = {c["id"]: c for c in components}
    if any(by_id[i]["health"] == isvc.UNAVAILABLE for i in _CORE if i in by_id):
        return "unavailable"
    if any(c["health"] in (isvc.UNAVAILABLE, isvc.DEGRADED) for c in components if c["id"] in _WATCHED):
        return "degraded"
    return "ok"


def system_health(db: Session) -> dict[str, Any]:
    items = isvc.list_integrations()
    components = [_component(i) for i in items if i["id"] in _CORE | _PIPELINE]
    components.append(_audit_chain(db))
    components.append(_rule_engine(db))
    external = [_component(i) for i in items if i["id"] not in _CORE | _PIPELINE]
    return {
        "status": overall_status(components),
        "checkedAt": datetime.now(timezone.utc).replace(tzinfo=None),
        "environment": settings.app_env,
        "version": "0.1.0",
        "components": components,
        "integrations": external,
        "integrationSummary": isvc.summarize(items),
        "activity": _activity(db),
        "warnings": _warnings(items),
    }
