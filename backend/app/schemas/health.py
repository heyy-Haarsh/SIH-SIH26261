from typing import Any

from app.schemas.base import CamelModel, SnakeModel


class HealthResponse(SnakeModel):
    status: str
    environment: str
    database: str
    storage_backend: str
    demo_auth: bool


class ComponentStatus(CamelModel):
    name: str
    status: str
    detail: str = ""


class AdminHealthResponse(SnakeModel):
    status: str
    environment: str
    database: str
    storage_backend: str
    demo_auth: bool
    task_runner: str
    components: list[ComponentStatus]
    counts: dict[str, int]
    notes: list[str]


class JobItem(CamelModel):
    id: str
    type: str
    application_id: str
    status: str
    created_at: Any
    completed_at: Any = None


class JobsResponse(CamelModel):
    runner_mode: str
    celery_enabled: bool
    note: str
    jobs: list[JobItem]
