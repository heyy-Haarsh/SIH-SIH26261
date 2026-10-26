from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models import AuditEvent, DeficiencyNotice, ReviewDecision
from app.repositories.base import BaseRepository


class ReviewRepository(BaseRepository):
    def decisions_for_application(self, application_id: str) -> list[ReviewDecision]:
        stmt = (
            select(ReviewDecision)
            .where(ReviewDecision.application_id == application_id)
            .options(joinedload(ReviewDecision.author))
            .order_by(ReviewDecision.created_at)
        )
        return list(self.db.scalars(stmt).unique())

    def deficiencies_for_application(self, application_id: str) -> list[DeficiencyNotice]:
        stmt = (
            select(DeficiencyNotice)
            .where(DeficiencyNotice.application_id == application_id)
            .order_by(DeficiencyNotice.created_at)
        )
        return list(self.db.scalars(stmt))


class AuditRepository(BaseRepository):
    def for_application(self, application_id: str, limit: int = 100, offset: int = 0) -> list[AuditEvent]:
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.application_id == application_id)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt))

    def list_all(self, limit: int = 100, offset: int = 0) -> list[AuditEvent]:
        stmt = (
            select(AuditEvent)
            .order_by(AuditEvent.created_at.desc(), AuditEvent.id)
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.scalars(stmt))
