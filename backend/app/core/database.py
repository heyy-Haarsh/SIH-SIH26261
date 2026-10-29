"""Database engine, session factory and declarative Base.

PostgreSQL is the intended production database. SQLite is allowed for local
demos only, and only when USE_SQLITE_FALLBACK=true is set explicitly.
"""

import logging
from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, URL, make_url
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import BASE_DIR, ConfigurationError, get_settings

logger = logging.getLogger("praman.db")

DEFAULT_SQLITE_URL = "sqlite:///./praman_dev.db"


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _resolve_sqlite_url(url: URL) -> URL:
    """Anchor relative SQLite file paths to backend/ so the CWD does not matter."""
    db = url.database
    if db and db != ":memory:" and not Path(db).is_absolute():
        return url.set(database=str((BASE_DIR / db).resolve()))
    return url


def _make_sqlite_engine(url: URL) -> Engine:
    url = _resolve_sqlite_url(url)
    eng = create_engine(
        url,
        connect_args={"check_same_thread": False},  # FastAPI uses a threadpool
        future=True,
    )

    @event.listens_for(eng, "connect")
    def _enable_fk(dbapi_conn, _record):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return eng


def build_engine() -> tuple[Engine, str]:
    """Return (engine, mode) where mode is 'postgresql', 'sqlite' or 'sqlite-fallback'."""
    settings = get_settings()
    url = make_url(settings.database_url)
    backend = url.get_backend_name()

    if backend == "sqlite":
        if not settings.use_sqlite_fallback:
            raise ConfigurationError(
                "SQLite is a development-only fallback. Set USE_SQLITE_FALLBACK=true "
                "explicitly, or configure a PostgreSQL DATABASE_URL."
            )
        logger.warning("Using SQLite development database (not for production).")
        return _make_sqlite_engine(url), "sqlite"

    # Non-SQLite (PostgreSQL intended)
    try:
        eng = create_engine(url, pool_pre_ping=True, future=True)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return eng, backend
    except Exception as exc:  # driver missing or server unreachable
        if settings.use_sqlite_fallback:
            logger.warning(
                "Database %s unavailable (%s); falling back to SQLite dev database.",
                backend,
                exc.__class__.__name__,
            )
            return _make_sqlite_engine(make_url(DEFAULT_SQLITE_URL)), "sqlite-fallback"
        raise ConfigurationError(f"Cannot connect to database ({backend}): {exc}") from exc


engine, DB_MODE = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create tables if missing (demo convenience; Alembic is the migration path)."""
    import app.models  # noqa: F401  (register all models on Base.metadata)

    Base.metadata.create_all(bind=engine)
    ensure_additive_columns()
    migrate_admin_role_to_regional_officer()


# Columns added after the first release. ``create_all`` never alters existing tables, so demo
# databases created by an older build are upgraded in place (additive, idempotent). Alembic
# remains the production migration path (see alembic/versions).
_ADDITIVE_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("applications", "institution_name", "VARCHAR(255) NOT NULL DEFAULT ''"),
    ("findings", "fingerprint", "VARCHAR(64) NOT NULL DEFAULT ''"),
    ("findings", "resolution_reason", "TEXT"),
    ("findings", "resolved_at", "DATETIME"),
    ("users", "last_delegated_at", "DATETIME"),
    ("deficiency_notices", "requires_replacement", "BOOLEAN NOT NULL DEFAULT 0"),
    ("handbook_references", "academic_year", "VARCHAR(32) NOT NULL DEFAULT ''"),
    ("handbook_references", "applicable_categories", "VARCHAR(255) NOT NULL DEFAULT ''"),
    ("application_categories", "info_fields", "JSON NOT NULL DEFAULT '[]'"),
    ("applications", "config_version_id", "VARCHAR(36)"),
    ("applications", "info_values", "JSON NOT NULL DEFAULT '{}'"),
    ("documents", "requirement_id", "VARCHAR(36)"),
)


def ensure_additive_columns(bind: Engine | None = None) -> None:
    from sqlalchemy import inspect

    target = bind or engine
    insp = inspect(target)
    for table, column, ddl in _ADDITIVE_COLUMNS:
        if table not in insp.get_table_names():
            continue
        existing = {c["name"] for c in insp.get_columns(table)}
        if column in existing:
            continue
        with target.begin() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
        logger.info("Added missing column %s.%s", table, column)


def migrate_admin_role_to_regional_officer(bind: Engine | None = None) -> None:
    """Rename legacy role value admin → regional_officer (string storage)."""
    target = bind or engine
    try:
        with target.begin() as conn:
            result = conn.execute(
                text("UPDATE users SET role = 'regional_officer' WHERE role = 'admin'")
            )
            if result.rowcount:
                logger.info("Migrated %s user(s) from admin → regional_officer", result.rowcount)
    except Exception as exc:  # noqa: BLE001 — demo DB may not have users yet
        logger.debug("admin→regional_officer migration skipped: %s", exc)


def database_status() -> str:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return "unavailable"
    if DB_MODE == "postgresql":
        return "postgresql"
    return "sqlite (dev fallback)"
