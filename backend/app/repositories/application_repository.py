from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from app.models import Application, DeficiencyNotice
from app.models.enums import ApplicationStatus, DeficiencyStatus
from app.repositories.base import BaseRepository

QUEUE_STATUSES = (
    ApplicationStatus.AWAITING_REVIEW,
    ApplicationStatus.UNDER_REVIEW,
    ApplicationStatus.DEFICIENCY,
    ApplicationStatus.MANUAL_REVIEW,
    ApplicationStatus.RESUBMITTED,
)


class ApplicationRepository(BaseRepository):
    _summary_opts = (
        joinedload(Application.institution),
        joinedload(Application.category),
        joinedload(Application.assigned_officer),
    )

    def get(self, application_id: str) -> Optional[Application]:
        stmt = (
            select(Application)
            .where(Application.id == application_id)
            .options(*self._summary_opts, selectinload(Application.documents))
        )
        return self.db.scalars(stmt).unique().first()

    def list(self, institution_id: Optional[str] = None) -> list[Application]:
        stmt = select(Application).options(*self._summary_opts)
        if institution_id is not None:
            stmt = stmt.where(Application.institution_id == institution_id)
        stmt = stmt.order_by(Application.submitted_at.desc().nulls_last(), Application.created_at.desc())
        return list(self.db.scalars(stmt).unique())

    def count(self) -> int:
        return self.db.scalar(select(func.count()).select_from(Application)) or 0

    def next_sequence(self) -> int:
        return self.count() + 1001

    def open_deficiency_counts(self) -> dict[str, int]:
        rows = self.db.execute(
            select(DeficiencyNotice.application_id, func.count())
            .where(DeficiencyNotice.status == DeficiencyStatus.OPEN)
            .group_by(DeficiencyNotice.application_id)
        ).all()
        return {app_id: n for app_id, n in rows}

    def status_counts(self) -> dict[ApplicationStatus, int]:
        rows = self.db.execute(
            select(Application.status, func.count()).group_by(Application.status)
        ).all()
        return {status: n for status, n in rows}

    def count_manual_review_in_queue(self) -> int:
        return (
            self.db.scalar(
                select(func.count())
                .select_from(Application)
                .where(Application.status.in_(QUEUE_STATUSES), Application.requires_manual_review.is_(True))
            )
            or 0
        )

    def count_with_open_deficiencies(self) -> int:
        return (
            self.db.scalar(
                select(func.count(func.distinct(DeficiencyNotice.application_id))).where(
                    DeficiencyNotice.status == DeficiencyStatus.OPEN
                )
            )
            or 0
        )
