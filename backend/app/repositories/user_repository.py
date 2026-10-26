from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models import ApplicationCategory, Institution, User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository):
    def get(self, user_id: str) -> Optional[User]:
        return self.db.get(User, user_id)

    def get_by_email(self, email: str) -> Optional[User]:
        return self.db.scalar(select(User).where(User.email == email))

    def list_all(self) -> list[User]:
        stmt = select(User).options(joinedload(User.institution)).order_by(User.role, User.name)
        return list(self.db.scalars(stmt).unique())


class InstitutionRepository(BaseRepository):
    def get(self, institution_id: str) -> Optional[Institution]:
        return self.db.get(Institution, institution_id)

    def get_by_code(self, code: str) -> Optional[Institution]:
        return self.db.scalar(select(Institution).where(Institution.code == code))


class CategoryRepository(BaseRepository):
    def get_by_code(self, code: str) -> Optional[ApplicationCategory]:
        return self.db.scalar(select(ApplicationCategory).where(ApplicationCategory.code == code))

    def list_all(self, only_active: bool = False) -> list[ApplicationCategory]:
        stmt = select(ApplicationCategory).order_by(ApplicationCategory.code)
        if only_active:
            stmt = stmt.where(ApplicationCategory.is_active.is_(True))
        return list(self.db.scalars(stmt))
