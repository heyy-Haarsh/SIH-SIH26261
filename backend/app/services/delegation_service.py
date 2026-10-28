"""Regional Officer → Scrutiny Officer load-balanced delegation.

Auto-assigns submitted applications to the least-burdened active officer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ForbiddenError, NotFoundError, UnprocessableError
from app.models.application import Application
from app.models.enums import ApplicationStatus, FindingStatus, UserRole
from app.models.user import User
from app.models.validation import Finding
from app.services.audit_service import record_audit
from app.services import findings_service

ACTIVE_STATUSES = (
    ApplicationStatus.SUBMITTED,
    ApplicationStatus.PROCESSING,
    ApplicationStatus.UNDER_SCRUTINY,
    ApplicationStatus.RESUBMITTED,
    ApplicationStatus.AWAITING_REVIEW,
    ApplicationStatus.UNDER_REVIEW,
    ApplicationStatus.MANUAL_REVIEW,
)

DEFAULT_WEIGHTS: dict[str, float] = {
    "active_count_weight": 3.0,
    "open_issues_weight": 1.0,
    "recency_weight": 0.5,
    "max_queue_cap": 20,
}

SETTING_KEY = "delegation.weights"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def get_weights(db: Session) -> dict[str, float]:
    from app.models.settings import SystemSetting

    row = db.query(SystemSetting).filter(SystemSetting.key == SETTING_KEY).first()
    raw: dict[str, Any] = {}
    if row is not None and isinstance(row.value, dict):
        raw = row.value
    out = dict(DEFAULT_WEIGHTS)
    for k, default in DEFAULT_WEIGHTS.items():
        if k in raw and raw[k] is not None:
            try:
                out[k] = float(raw[k])
            except (TypeError, ValueError):
                out[k] = default
    out["max_queue_cap"] = max(1, int(out["max_queue_cap"]))
    return out


def set_weights(db: Session, user: User, payload: dict[str, Any]) -> dict[str, float]:
    if user.role != UserRole.REGIONAL_OFFICER:
        raise ForbiddenError("Only the regional officer can change delegation settings.")
    from app.models.settings import SystemSetting

    merged = get_weights(db)
    for k in DEFAULT_WEIGHTS:
        if k in payload and payload[k] is not None:
            merged[k] = float(payload[k])
    merged["max_queue_cap"] = max(1, int(merged["max_queue_cap"]))
    row = db.query(SystemSetting).filter(SystemSetting.key == SETTING_KEY).first()
    if row is None:
        row = SystemSetting(
            key=SETTING_KEY,
            value=merged,
            description="Load-balancing weights for scrutiny officer auto-delegation.",
            change_reason="regional officer update",
            updated_by_id=user.id,
        )
        db.add(row)
    else:
        row.value = merged
        row.updated_by_id = user.id
        row.change_reason = "regional officer update"
    record_audit(
        db,
        action="delegation.settings_updated",
        actor=user.name,
        actor_id=user.id,
        actor_role=user.role.value,
        detail=str(merged),
    )
    db.commit()
    return merged


def eligible_officers(db: Session) -> list[User]:
    return (
        db.query(User)
        .filter(User.role == UserRole.OFFICER, User.is_active.is_(True))
        .order_by(User.name.asc())
        .all()
    )


def officer_load(db: Session, officer_id: str) -> dict[str, Any]:
    active_count = (
        db.query(func.count(Application.id))
        .filter(
            Application.assigned_officer_id == officer_id,
            Application.status.in_(ACTIVE_STATUSES),
        )
        .scalar()
        or 0
    )
    open_issues = 0
    app_ids = [
        a.id
        for a in db.query(Application.id)
        .filter(
            Application.assigned_officer_id == officer_id,
            Application.status.in_(ACTIVE_STATUSES),
        )
        .all()
    ]
    for app_id in app_ids:
        open_issues += sum(
            1
            for f in findings_service.current_findings(db, app_id)
            if (f.status.value if hasattr(f.status, "value") else str(f.status))
            == FindingStatus.OPEN.value
        )

    officer = db.get(User, officer_id)
    last_assigned = getattr(officer, "last_delegated_at", None) if officer else None
    if last_assigned is None:
        # Fallback: most recent assignment among their apps
        last_assigned = (
            db.query(func.max(Application.updated_at))
            .filter(Application.assigned_officer_id == officer_id)
            .scalar()
        )
    return {
        "active_count": int(active_count),
        "open_issues": int(open_issues),
        "last_assigned_at": last_assigned,
    }


def select_officer(db: Session) -> User | None:
    weights = get_weights(db)
    w_count = weights["active_count_weight"]
    w_issues = weights["open_issues_weight"]
    w_recency = weights["recency_weight"]
    max_cap = int(weights["max_queue_cap"])
    now = _now()
    scored: list[tuple[float, datetime, User]] = []
    for officer in eligible_officers(db):
        load = officer_load(db, officer.id)
        if load["active_count"] >= max_cap:
            continue
        last = load["last_assigned_at"] or datetime(1970, 1, 1, tzinfo=timezone.utc)
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        hours_since = max(0.0, (now - last).total_seconds() / 3600.0)
        score = load["active_count"] * w_count + load["open_issues"] * w_issues - hours_since * w_recency
        scored.append((score, last, officer))
    if not scored:
        return None
    scored.sort(key=lambda x: (x[0], x[1]))
    return scored[0][2]


def list_officers_with_load(db: Session, user: User) -> list[dict[str, Any]]:
    if user.role != UserRole.REGIONAL_OFFICER:
        raise ForbiddenError("Only the regional officer can view officer workload.")
    weights = get_weights(db)
    cap = int(weights["max_queue_cap"])
    out: list[dict[str, Any]] = []
    for officer in eligible_officers(db):
        load = officer_load(db, officer.id)
        out.append(
            {
                "id": officer.id,
                "name": officer.name,
                "email": officer.email,
                "isActive": officer.is_active,
                "activeCount": load["active_count"],
                "openIssues": load["open_issues"],
                "lastAssignedAt": load["last_assigned_at"],
                "maxQueueCap": cap,
                "isAtCap": load["active_count"] >= cap,
            }
        )
    return out


def unassigned_queue(db: Session, user: User) -> list[Application]:
    if user.role != UserRole.REGIONAL_OFFICER:
        raise ForbiddenError("Only the regional officer can view the delegation queue.")
    return (
        db.query(Application)
        .filter(
            Application.assigned_officer_id.is_(None),
            Application.status.in_(
                (
                    ApplicationStatus.SUBMITTED,
                    ApplicationStatus.PROCESSING,
                    ApplicationStatus.RESUBMITTED,
                    ApplicationStatus.AWAITING_REVIEW,
                )
            ),
        )
        .order_by(Application.submitted_at.asc().nulls_last(), Application.created_at.asc())
        .all()
    )


def officer_queue(db: Session, user: User, officer_id: str) -> list[Application]:
    if user.role != UserRole.REGIONAL_OFFICER:
        raise ForbiddenError("Only the regional officer can inspect officer queues.")
    officer = db.get(User, officer_id)
    if officer is None or officer.role != UserRole.OFFICER:
        raise NotFoundError("Scrutiny officer not found.")
    return (
        db.query(Application)
        .filter(Application.assigned_officer_id == officer_id)
        .order_by(Application.submitted_at.desc().nulls_last())
        .all()
    )


def delegate(
    db: Session,
    actor: User | None,
    application_id: str,
    *,
    officer_id: str | None = None,
    auto: bool = False,
) -> Application:
    app = db.get(Application, application_id)
    if app is None:
        raise NotFoundError("Application not found.")
    if officer_id:
        if actor is None or actor.role != UserRole.REGIONAL_OFFICER:
            raise ForbiddenError("Only the regional officer can manually assign applications.")
        officer = db.get(User, officer_id)
        if officer is None or officer.role != UserRole.OFFICER or not officer.is_active:
            raise UnprocessableError("Choose an active scrutiny officer.")
    else:
        officer = select_officer(db)
        if officer is None:
            raise UnprocessableError(
                "No eligible scrutiny officer is available (all at capacity or none active).",
                code="no_eligible_officer",
            )
    app.assigned_officer_id = officer.id
    officer.last_delegated_at = _now()
    actor_name = actor.name if actor else "system"
    actor_id = actor.id if actor else None
    actor_role = actor.role.value if actor else "system"
    record_audit(
        db,
        action="delegation.assigned",
        actor=actor_name,
        actor_id=actor_id,
        actor_role=actor_role,
        detail=(
            f"Assigned {app.application_number} to {officer.name}"
            + (" (auto)" if auto or not officer_id else " (manual)")
        ),
        application_id=app.id,
    )
    db.commit()
    db.refresh(app)
    return app


def try_auto_delegate(db: Session, application_id: str) -> Application | None:
    """Best-effort auto-assign. Never fails the submit path if no officer is free."""
    settings = get_settings()
    if not getattr(settings, "auto_delegate", True):
        return None
    app = db.get(Application, application_id)
    if app is None or app.assigned_officer_id:
        return app
    try:
        return delegate(db, None, application_id, auto=True)
    except UnprocessableError:
        record_audit(
            db,
            action="delegation.unassigned",
            actor="system",
            actor_role="system",
            detail=f"{app.application_number} remains unassigned — no eligible officer",
            application_id=app.id,
        )
        db.commit()
        return app


def bulk_delegate(
    db: Session,
    actor: User,
    application_ids: list[str] | None = None,
) -> list[dict[str, Any]]:
    if actor.role != UserRole.REGIONAL_OFFICER:
        raise ForbiddenError("Only the regional officer can bulk-delegate.")
    if application_ids is None:
        ids = [a.id for a in unassigned_queue(db, actor)]
    else:
        ids = application_ids
    results: list[dict[str, Any]] = []
    for app_id in ids:
        try:
            app = delegate(db, actor, app_id, auto=True)
            officer = app.assigned_officer
            results.append(
                {
                    "applicationId": app.id,
                    "applicationNumber": app.application_number,
                    "ok": True,
                    "officerId": officer.id if officer else None,
                    "officerName": officer.name if officer else None,
                }
            )
        except Exception as exc:  # noqa: BLE001 — per-row result
            results.append(
                {
                    "applicationId": app_id,
                    "ok": False,
                    "error": str(exc),
                }
            )
    return results
