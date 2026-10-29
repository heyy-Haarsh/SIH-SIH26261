from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import CamelModel


class ReadinessItemOut(CamelModel):
    code: str
    title: str
    detail: str = ""
    requirement_code: str | None = None


class ReadinessOut(CamelModel):
    application_id: str
    status: str
    is_draft: bool
    must_fix: list[ReadinessItemOut] = Field(default_factory=list)
    review_recommended: list[ReadinessItemOut] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    can_submit: bool
    # The applicant's own attestations, listed by the server so the UI never invents them.
    declarations: list[str] = Field(default_factory=list)


class SubmitIn(BaseModel):
    # Must be true to submit; repeating a submit on an already-submitted application is still safe.
    confirm_declarations: bool = False


class SubmitResultOut(CamelModel):
    application_id: str
    status: str
    already_submitted: bool
    submitted_at: datetime | None = None
    message: str = ""
    warnings: list[str] = Field(default_factory=list)
