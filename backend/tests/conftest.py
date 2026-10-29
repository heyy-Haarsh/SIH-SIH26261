import os
from pathlib import Path

import pytest

TEST_DB = Path(__file__).resolve().parent / "test_praman.db"
TEST_UPLOADS = Path(__file__).resolve().parent / "_test_uploads"

# Must set before importing application modules
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB.as_posix()}"
os.environ["USE_SQLITE_FALLBACK"] = "true"
os.environ["DEMO_AUTH_ENABLED"] = "true"
os.environ["UPLOAD_DIR"] = str(TEST_UPLOADS)
os.environ["APP_ENV"] = "test"
os.environ["USE_SIMULATED_HTTP_ISSUERS"] = "false"
os.environ["ENABLE_LIVE_VERIFICATION"] = "false"

# Clear cached settings / engines if re-imported in same session
from app.core.config import get_settings

get_settings.cache_clear()

if TEST_DB.exists():
    TEST_DB.unlink()

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


DEMO_OFFICER_ID = "usr-off-001"


@pytest.fixture(autouse=True)
def _deterministic_officer_assignment(request, monkeypatch):
    """Auto-delegation load-balances across officers. Most tests model a single demo officer
    who sees every submission, so pin assignment to that officer. `test_delegation.py` exercises
    the real load balancer and is left untouched."""
    if request.node.fspath.basename == "test_delegation.py":
        return
    from app.models.user import User
    from app.services import delegation_service

    monkeypatch.setattr(
        delegation_service,
        "select_officer",
        lambda db: db.get(User, DEMO_OFFICER_ID),
    )


@pytest.fixture()
def client():
    TEST_UPLOADS.mkdir(parents=True, exist_ok=True)
    with TestClient(app) as c:
        yield c


def auth_headers(role: str) -> dict[str, str]:
    return {"X-Demo-Role": role, "X-Demo-User-Id": f"demo-{role}"}
