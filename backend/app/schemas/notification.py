from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.common import CamelModel


class NotificationOut(CamelModel):
    id: str
    kind: str
    title: str
    body: str = ""
    application_id: str | None = None
    link: str | None = None
    created_at: datetime
    read_at: datetime | None = None
    is_read: bool = False


class NotificationListOut(CamelModel):
    items: list[NotificationOut] = Field(default_factory=list)
    unread_count: int = 0
