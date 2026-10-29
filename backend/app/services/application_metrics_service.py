"""Application counts shown on the officer and administrator dashboards.

Both dashboards read this single function, so the same application is never counted under
different statuses depending on which screen you open. A scrutiny officer's counts cover only the
applications delegated to them (the same scope as their application list); the regional officer
sees the whole region.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.enums import ApplicationStatus, DeficiencyStatus, UserRole
from app.models.review import DeficiencyNotice
from app.models.user import User
from app.services import status_model as sm


def application_metrics(db: Session, user: User | None = None) -> dict:
    scoped = user is not None and user.role == UserRole.OFFICER

    # Unsubmitted drafts are private to the applicant and never counted for staff.
    rows_query = db.query(Application.status, Application.requires_manual_review).filter(
        Application.status != ApplicationStatus.DRAFT
    )
    if scoped:
        rows_query = rows_query.filter(Application.assigned_officer_id == user.id)
    rows = rows_query.all()

    by_status: dict[str, int] = {}
    by_stage = {stage: 0 for stage in sm.STAGE_LABELS}
    manual_review = 0
    for status, manual in rows:
        value = sm._value(status)
        stage = sm.stage_of(value)
        by_status[value] = by_status.get(value, 0) + 1
        by_stage[stage] += 1
        if manual and stage in sm.OFFICER_QUEUE_STAGES:
            manual_review += 1

    clarifications_query = (
        db.query(func.count(DeficiencyNotice.id))
        .join(Application, Application.id == DeficiencyNotice.application_id)
        .filter(
            DeficiencyNotice.status == DeficiencyStatus.OPEN,
            Application.status != ApplicationStatus.DRAFT,
        )
    )
    if scoped:
        clarifications_query = clarifications_query.filter(Application.assigned_officer_id == user.id)
    open_clarifications = clarifications_query.scalar() or 0

    return {
        "total": len(rows),
        "inOfficerQueue": sum(by_stage[s] for s in sm.OFFICER_QUEUE_STAGES),
        "byStage": by_stage,
        "stageLabels": dict(sm.STAGE_LABELS),
        "byStatus": by_status,
        "requiresManualReview": manual_review,
        "openClarifications": open_clarifications,
    }
