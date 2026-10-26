"""Demo authentication and server-side RBAC.

Demo auth is NOT real authentication. When DEMO_AUTH_ENABLED=true the caller
identifies itself with two headers:

    X-Demo-Role:     applicant | officer | admin
    X-Demo-User-Id:  a user id, a user email, or an alias like ``demo-officer``

Both are required. The user is looked up in the database and the *database* role
is authoritative: the claimed role header must equal the stored role of the
resolved user, otherwise the request is rejected. A role header alone (or a
frontend role switcher) therefore never grants access by itself. Every route
enforces its own role requirement through ``require_roles``; application-level
ownership is enforced through ``ensure_application_access``.
"""

from typing import Callable, Optional

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import ForbiddenError, NotFoundError, UnauthorizedError
from app.models import Application, User
from app.models.enums import UserRole

# Aliases used by the frontend demo role switcher -> seeded demo users.
DEMO_USER_ALIASES: dict[str, str] = {
    "demo-applicant": "usr-app-001",
    "demo-officer": "usr-off-001",
    "demo-admin": "usr-adm-001",
}


def _parse_role(raw: str) -> UserRole:
    try:
        return UserRole(raw.strip().lower())
    except ValueError:
        raise UnauthorizedError(
            "Invalid X-Demo-Role. Allowed roles: applicant, officer, admin.", code="invalid_role"
        ) from None


def get_current_user(
    db: Session = Depends(get_db),
    x_demo_role: Optional[str] = Header(default=None),
    x_demo_user_id: Optional[str] = Header(default=None),
) -> User:
    if not settings.demo_auth_enabled:
        raise UnauthorizedError(
            "Authentication is not configured: demo auth is disabled and no real identity "
            "provider is implemented.",
            code="auth_not_configured",
        )
    if not x_demo_role or not x_demo_user_id:
        raise UnauthorizedError(
            "Missing X-Demo-Role and/or X-Demo-User-Id header.", code="missing_credentials"
        )

    claimed_role = _parse_role(x_demo_role)
    ident = x_demo_user_id.strip()
    user_id = DEMO_USER_ALIASES.get(ident.lower(), ident)

    user = db.get(User, user_id)
    if user is None:
        user = db.scalar(select(User).where(User.email == ident.lower()))
    if user is None:
        raise UnauthorizedError("Unknown demo user.", code="unknown_user")
    if not user.is_active:
        raise ForbiddenError("User account is disabled.", code="user_disabled")
    if user.role != claimed_role:
        raise ForbiddenError(
            "Claimed role does not match the role assigned to this user.", code="role_mismatch"
        )
    return user


def require_roles(*roles: UserRole) -> Callable[..., User]:
    """Dependency factory: the authenticated user must hold one of ``roles``."""
    allowed = frozenset(roles)

    def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise ForbiddenError(
                f"Role '{user.role.value}' is not permitted to perform this action.",
                code="insufficient_role",
            )
        return user

    return _dep


require_applicant = require_roles(UserRole.APPLICANT)
require_officer = require_roles(UserRole.OFFICER)
require_admin = require_roles(UserRole.ADMIN)
require_applicant_or_officer = require_roles(UserRole.APPLICANT, UserRole.OFFICER)
require_officer_or_admin = require_roles(UserRole.OFFICER, UserRole.ADMIN)
require_any_role = require_roles(UserRole.APPLICANT, UserRole.OFFICER, UserRole.ADMIN)


def can_access_application(user: User, application: Application) -> bool:
    """Read access: applicants only for their own institution; officers and admins for all."""
    if user.role in (UserRole.OFFICER, UserRole.ADMIN):
        return True
    if user.role == UserRole.APPLICANT:
        return user.institution_id is not None and user.institution_id == application.institution_id
    return False


def ensure_application_access(user: User, application: Application) -> None:
    """Raise 404 (not 403) for other institutions' applications so ids cannot be probed."""
    if not can_access_application(user, application):
        if user.role == UserRole.APPLICANT:
            raise NotFoundError("Application not found.")
        raise ForbiddenError(
            f"Role '{user.role.value}' cannot access application data.", code="insufficient_role"
        )
