from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Finding, ValidationRun, VerificationRequest
from app.models.enums import ValidationRunStatus
from app.repositories.base import BaseRepository


class ValidationRepository(BaseRepository):
    def get(self, run_id: str) -> Optional[ValidationRun]:
        stmt = (
            select(ValidationRun)
            .where(ValidationRun.id == run_id)
            .options(selectinload(ValidationRun.findings).selectinload(Finding.evidence))
        )
        return self.db.scalars(stmt).first()

    def list_for_application(self, application_id: str) -> list[ValidationRun]:
        stmt = (
            select(ValidationRun)
            .where(ValidationRun.application_id == application_id)
            .options(selectinload(ValidationRun.findings).selectinload(Finding.evidence))
            .order_by(ValidationRun.created_at.desc())
        )
        return list(self.db.scalars(stmt))

    def latest_for_application(
        self, application_id: str, completed_only: bool = True
    ) -> Optional[ValidationRun]:
        stmt = (
            select(ValidationRun)
            .where(ValidationRun.application_id == application_id)
            .options(selectinload(ValidationRun.findings).selectinload(Finding.evidence))
            .order_by(ValidationRun.created_at.desc())
            .limit(1)
        )
        if completed_only:
            stmt = stmt.where(ValidationRun.status == ValidationRunStatus.COMPLETED)
        return self.db.scalars(stmt).first()

    def recent(self, limit: int = 25) -> list[ValidationRun]:
        stmt = select(ValidationRun).order_by(ValidationRun.created_at.desc()).limit(limit)
        return list(self.db.scalars(stmt))


class VerificationRepository(BaseRepository):
    def for_run(self, run_id: str) -> list[VerificationRequest]:
        stmt = (
            select(VerificationRequest)
            .where(VerificationRequest.validation_run_id == run_id)
            .order_by(VerificationRequest.created_at, VerificationRequest.claim)
        )
        return list(self.db.scalars(stmt))

    def for_application(self, application_id: str) -> list[VerificationRequest]:
        stmt = (
            select(VerificationRequest)
            .where(VerificationRequest.application_id == application_id)
            .order_by(VerificationRequest.created_at.desc())
        )
        return list(self.db.scalars(stmt))
