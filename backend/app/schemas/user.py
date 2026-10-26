from typing import Optional

from app.models.enums import UserRole
from app.schemas.base import CamelModel


class UserOut(CamelModel):
    id: str
    name: str
    email: str
    role: UserRole
    institution_id: Optional[str] = None
    institution_name: Optional[str] = None
    is_active: Optional[bool] = None


class InstitutionOut(CamelModel):
    id: str
    name: str
    code: str
    state: str
    type: str
