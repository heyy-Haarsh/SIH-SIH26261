"""Application counts shown on the officer and administrator dashboards.

Both dashboards read this single function, so the same application is never counted under
different statuses depending on which screen you open.
"""

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.enums import DeficiencyStatus
from app.models.review import DeficiencyNotice
from app.services import status_model as sm


def application_metrics(db: Session) -> dict:
    rows = db.query(Application.status, Application.requires_manual_review).all()
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

    open_clarifications = (
        db.query(func.count(DeficiencyNotice.id))
        .filter(DeficiencyNotice.status == DeficiencyStatus.OPEN)
        .scalar()
        or 0
    )
    return {
        "total": len(rows),
        "inOfficerQueue": sum(by_stage[s] for s in sm.OFFICER_QUEUE_STAGES),
        "byStage": by_stage,
        "stageLabels": dict(sm.STAGE_LABELS),
        "byStatus": by_status,
        "requiresManualReview": manual_review,
        "openClarifications": open_clarifications,
    }
