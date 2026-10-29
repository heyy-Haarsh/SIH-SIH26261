"""One place that maps backend application states to what the institution sees.

Every dashboard count, status chip, timeline and "next action" is derived from here so the
screens cannot drift apart. Nothing here invents a state: a stage is only shown as reached when
the application's persisted status or a recorded audit event says so.

A recorded outcome ("decision_recorded") is the scrutiny officer's recommendation or rejection.
It is not an official regulatory approval and is never worded as one.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.audit import AuditEvent
from app.schemas.common import ApplicantLifecycleStepOut

# backend status -> stage
STATUS_TO_STAGE: dict[str, str] = {
    "draft": "draft",
    "submitted": "submitted",
    "processing": "processing",
    "under_scrutiny": "scrutiny",
    "awaiting_review": "scrutiny",
    "under_review": "scrutiny",
    "manual_review": "scrutiny",
    "clarification_required": "applicant_action",
    "deficiency": "applicant_action",
    "resubmitted": "resubmitted",
    "recommended": "decision_recorded",
    "rejected": "decision_recorded",
    "approved": "decision_recorded",
}

STAGE_LABEL: dict[str, str] = {
    "draft": "Draft",
    "submitted": "Submitted",
    "processing": "Automatic checks",
    "scrutiny": "Under scrutiny",
    "applicant_action": "Action required",
    "resubmitted": "Resubmitted",
    "decision_recorded": "Decision recorded",
}

# Order used by the timeline. applicant_action / resubmitted only appear when they really happened.
_ORDER = ["draft", "submitted", "processing", "scrutiny", "applicant_action", "resubmitted", "decision_recorded"]
_CORE = {"draft", "submitted"}

# stage -> audit actions that prove it happened (first/last occurrence is used as the timestamp)
_EVIDENCE: dict[str, tuple[str, ...]] = {
    "processing": ("workflow.processing_started",),
    "scrutiny": ("workflow.under_scrutiny", "workflow.start_scrutiny"),
    "applicant_action": ("workflow.clarification_requested",),
    "resubmitted": ("workflow.resubmitted",),
    "decision_recorded": ("workflow.recommended", "workflow.rejected"),
}

ACTIVE_STAGES = {"submitted", "processing", "scrutiny", "applicant_action", "resubmitted"}
SCRUTINY_STAGES = {"scrutiny", "resubmitted"}


def status_value(app: Application) -> str:
    return app.status.value if hasattr(app.status, "value") else str(app.status)


def stage_of(status: str) -> str:
    return STATUS_TO_STAGE.get(status, "submitted")


def stage_label(stage: str) -> str:
    return STAGE_LABEL.get(stage, stage.replace("_", " ").title())


def lifecycle_steps(db: Session, app: Application) -> list[ApplicantLifecycleStepOut]:
    stage = stage_of(status_value(app))
    events = (
        db.query(AuditEvent.action, AuditEvent.created_at)
        .filter(
            AuditEvent.application_id == app.id,
            AuditEvent.action.in_([a for acts in _EVIDENCE.values() for a in acts]),
        )
        .order_by(AuditEvent.created_at)
        .all()
    )
    at: dict[str, datetime] = {}
    for key, actions in _EVIDENCE.items():
        times = [e.created_at for e in events if e.action in actions]
        if times:
            # Repeatable stages show the latest occurrence; the rest show when they first happened.
            at[key] = times[-1] if key in ("applicant_action", "resubmitted", "decision_recorded") else times[0]
    at["draft"] = app.created_at
    if app.submitted_at:
        at["submitted"] = app.submitted_at

    current_index = _ORDER.index(stage)
    steps: list[ApplicantLifecycleStepOut] = []
    for index, key in enumerate(_ORDER):
        happened = key in at
        if key == stage:
            state = "current"
        elif happened:
            state = "done"
        elif index < current_index and key in _CORE:
            state = "done"
        elif index < current_index:
            continue  # skipped with no record of it — do not invent it
        elif key in ("applicant_action", "resubmitted"):
            continue  # only shown when it actually occurs
        else:
            state = "upcoming"
        steps.append(
            ApplicantLifecycleStepOut(
                key=key,
                label=stage_label(key),
                state=state,
                at=at.get(key),
            )
        )
    return steps
