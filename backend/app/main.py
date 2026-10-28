from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import (
    admin,
    applicant,
    applications,
    doc_verification,
    extraction,
    forensics,
    health,
    reconciliation,
    scrutiny,
    workflow,
)
from app.core import runtime_config
from app.core.config import get_settings
from app.core.database import SessionLocal, init_db
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.seed import ensure_regional_demo_users, seed_if_empty


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    settings = get_settings()
    settings.validate_runtime()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    init_db()
    db = SessionLocal()
    try:
        seed_if_empty(db)
        ensure_regional_demo_users(db)
        runtime_config.load_from_db(db)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    application = FastAPI(
        title=settings.app_name,
        description=(
            "PRAMAN — AI-assisted application validation and regulatory compliance platform "
            "(SIH26261). Demo auth is for local development only."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router, prefix="/api/v1")
    application.include_router(applications.router, prefix="/api/v1")
    application.include_router(applicant.router, prefix="/api/v1")
    application.include_router(scrutiny.router, prefix="/api/v1")
    application.include_router(extraction.router, prefix="/api/v1")
    application.include_router(reconciliation.router, prefix="/api/v1")
    application.include_router(forensics.router, prefix="/api/v1")
    application.include_router(workflow.router, prefix="/api/v1")
    application.include_router(doc_verification.router, prefix="/api/v1")
    application.include_router(admin.router, prefix="/api/v1")
    # Single set of handlers (includes logging for unhandled errors; no stack traces to clients)
    register_exception_handlers(application)

    return application


app = create_app()
