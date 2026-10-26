from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import RegulatoryRule
from app.repositories.base import BaseRepository


class RuleRepository(BaseRepository):
    def list_all(self, only_active: bool = False) -> list[RegulatoryRule]:
        stmt = select(RegulatoryRule).options(selectinload(RegulatoryRule.versions)).order_by(RegulatoryRule.code)
        if only_active:
            stmt = stmt.where(RegulatoryRule.is_active.is_(True))
        return list(self.db.scalars(stmt))

    def get(self, rule_id: str) -> Optional[RegulatoryRule]:
        return self.db.get(RegulatoryRule, rule_id)

    def get_by_code(self, code: str) -> Optional[RegulatoryRule]:
        return self.db.scalar(select(RegulatoryRule).where(RegulatoryRule.code == code))
