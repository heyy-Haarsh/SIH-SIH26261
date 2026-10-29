"""Backend RBAC matrix.

Every route must be listed in POLICY with the roles that may call it. A route that is added
without a policy entry fails ``test_every_route_has_an_explicit_policy`` so access is always a
conscious decision. Denied roles must get 403 and anonymous callers 401, enforced by the API
itself — not by the UI hiding a button.
"""

import re

import pytest

from app.core.database import SessionLocal
from app.main import app
from app.models.enums import UserRole
from app.models.user import Institution, User
from tests.conftest import auth_headers

A, O, ADM = "applicant", "officer", "regional_officer"
STAFF = {O, ADM}
ANY = {A, O, ADM}
PUBLIC = "public"

# (method, path-after-/api/v1) -> allowed roles. Application/document-scoped "ANY" routes also
# restrict applicants to their own institution (covered by the tenant test below).
POLICY: dict[tuple[str, str], object] = {
    ("GET", "/health"): PUBLIC,
    # --- applicant-only
    ("GET", "/applicant/applications"): {A},
    ("GET", "/applicant/applications/{application_id}"): {A},
    ("GET", "/applicant/overview"): {A},
    ("GET", "/applicant/clarifications"): {A},
    ("GET", "/applicant/findings/{finding_id}/evidence"): {A},
    ("PATCH", "/applications/{application_id}"): {A},
    ("POST", "/applications"): {A},
    ("POST", "/applications/{application_id}/documents"): {A},
    ("POST", "/applications/{application_id}/resubmit"): {A},
    ("GET", "/applications/{application_id}/readiness"): {A},
    ("POST", "/applications/{application_id}/submit"): {A},
    ("POST", "/deficiencies/{deficiency_id}/respond"): {A},
    # --- shared, but data-scoped to the caller's institution
    ("GET", "/applications/upload-policy"): ANY,
    ("GET", "/applications/categories"): ANY,
    ("GET", "/applications/categories/{category_code}/config"): ANY,
    # --- in-app notifications: every role, always scoped to the caller's own inbox
    ("POST", "/findings/{finding_id}/transition"): {O},
    ("GET", "/findings/{finding_id}/history"): STAFF,
    ("GET", "/notifications"): ANY,
    ("POST", "/notifications/read-all"): ANY,
    ("POST", "/notifications/{notification_id}/read"): ANY,
    ("POST", "/scrutiny/transcribe"): STAFF,
    ("GET", "/applications/{application_id}/deficiencies"): ANY,
    ("GET", "/deficiencies"): ANY,
    ("GET", "/documents/{document_id}/file"): ANY,
    # --- officer / regional officer: internal scrutiny data (never shown to applicants).
    # Decisions and resolutions are officer-only: the regional officer configures the system
    # but does not decide applications (separation of duties).
    ("GET", "/applications"): STAFF,
    ("GET", "/applications/metrics"): STAFF,
    ("GET", "/applications/{application_id}"): STAFF,
    ("POST", "/applications/{application_id}/validation-runs"): STAFF,
    ("GET", "/applications/{application_id}/document-verification"): STAFF,
    ("POST", "/applications/{application_id}/document-verification"): STAFF,
    ("POST", "/documents/{document_id}/document-verification"): STAFF,
    ("GET", "/document-verification-runs/{run_id}"): STAFF,
    ("GET", "/document-verification/configs"): STAFF,
    ("POST", "/document-verification-checks/{check_id}/resolve"): {O},
    ("POST", "/documents/{document_id}/extraction-runs"): STAFF,
    ("GET", "/documents/{document_id}/extraction-runs/latest"): STAFF,
    ("GET", "/extraction-runs/{run_id}"): STAFF,
    ("GET", "/extraction-runs/{run_id}/fields"): STAFF,
    ("GET", "/extraction/ocr-capability"): STAFF,
    ("POST", "/extracted-fields/{field_id}/corrections"): {O},
    ("POST", "/applications/{application_id}/forensics-runs"): STAFF,
    ("GET", "/applications/{application_id}/forensics-runs/latest"): STAFF,
    ("GET", "/applications/{application_id}/forensics-indicators"): STAFF,
    ("POST", "/forensics-indicators/{indicator_id}/resolve"): {O},
    ("POST", "/applications/{application_id}/reconciliation-runs"): STAFF,
    ("GET", "/applications/{application_id}/reconciliation-runs/latest"): STAFF,
    ("GET", "/applications/{application_id}/reconciliation-items"): STAFF,
    ("POST", "/reconciliation-items/{item_id}/resolve"): {O},
    ("GET", "/applications/{application_id}/scrutiny-review"): STAFF,
    ("GET", "/applications/{application_id}/documents/{document_id}/report"): STAFF,
    ("GET", "/applications/{application_id}/report.json"): STAFF,
    ("GET", "/applications/{application_id}/report.pdf"): STAFF,
    ("POST", "/applications/{application_id}/scrutiny/start"): {O},
    ("POST", "/applications/{application_id}/scrutiny/clarification"): {O},
    ("POST", "/applications/{application_id}/scrutiny/decision"): {O},
    ("POST", "/applications/{application_id}/scrutiny/notes"): {O},
    ("POST", "/applications/{application_id}/scrutiny/refresh-summary"): STAFF,
    ("POST", "/findings/{finding_id}/resolve"): {O},
    # --- admin read-only reference data that officers may also see
    ("GET", "/admin/categories"): STAFF,
    ("GET", "/admin/rules"): STAFF,
    ("GET", "/applications/{application_id}/rule-checks"): STAFF,
}


def _policy_for(method: str, path: str):
    if (method, path) in POLICY:
        return POLICY[(method, path)]
    if path.startswith("/admin/"):
        return {ADM}
    return None


def _all_routes() -> list[tuple[str, str]]:
    out = []
    for path, methods in app.openapi()["paths"].items():
        rel = path.removeprefix("/api/v1")
        for method in methods:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                out.append((method.upper(), rel))
    return sorted(out)


def _fill(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "does-not-exist", path)


def test_every_route_has_an_explicit_policy():
    missing = [r for r in _all_routes() if _policy_for(*r) is None]
    assert not missing, f"Routes without an RBAC policy entry: {missing}"


def test_policy_has_no_stale_entries():
    live = set(_all_routes())
    stale = [k for k in POLICY if k not in live]
    assert not stale, f"Policy entries for routes that no longer exist: {stale}"


def _call(client, method: str, path: str, headers: dict | None):
    url = "/api/v1" + _fill(path)
    kwargs = {"headers": headers or {}}
    if method in {"POST", "PUT", "PATCH"}:
        kwargs["json"] = {}
    return client.request(method, url, **kwargs)


@pytest.mark.parametrize("method,path", _all_routes())
def test_route_enforces_roles(client, method, path):
    policy = _policy_for(method, path)
    assert policy is not None
    if policy == PUBLIC:
        assert _call(client, method, path, None).status_code == 200
        return

    anonymous = _call(client, method, path, None)
    assert anonymous.status_code == 401, f"{method} {path} anonymous -> {anonymous.status_code}"

    for role in (A, O, ADM):
        res = _call(client, method, path, auth_headers(role))
        denied = res.status_code == 403 and res.json().get("code") == "insufficient_role"
        if role in policy:
            assert not denied, f"{method} {path} wrongly denies {role}"
        else:
            assert res.status_code == 403, f"{method} {path} allows {role} ({res.status_code})"


# ---------------------------------------------------------------- tenant isolation + leakage


@pytest.fixture()
def other_applicant():
    """An applicant from a different institution."""
    with SessionLocal() as db:
        if not db.get(Institution, "inst-rbac-2"):
            db.add(
                Institution(
                    id="inst-rbac-2",
                    name="Other Institute",
                    code="OTHER-RBAC-2",
                    state="Maharashtra",
                    type="Engineering",
                )
            )
        if not db.get(User, "usr-app-rbac-2"):
            db.add(
                User(
                    id="usr-app-rbac-2",
                    name="Other Registrar",
                    email="registrar@other-rbac.edu",
                    role=UserRole.APPLICANT,
                    institution_id="inst-rbac-2",
                )
            )
        db.commit()
    yield {"X-Demo-Role": "applicant", "X-Demo-User-Id": "usr-app-rbac-2"}


def _make_app_with_doc(client):
    created = client.post(
        "/api/v1/applications",
        headers=auth_headers("applicant"),
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Test Institute of Technology",
            "program_name": "B.Tech",
            "academic_year": "2025-26",
        },
    ).json()
    up = client.post(
        f"/api/v1/applications/{created['id']}/documents",
        headers=auth_headers("applicant"),
        files={"file": ("affidavit.pdf", b"%PDF-1.4 rbac", "application/pdf")},
        data={"requirement_code": "AFFIDAVIT"},
    )
    assert up.status_code == 200, up.text
    return created["id"], up.json()


def test_applicant_cannot_reach_another_institutions_data(client, other_applicant):
    app_id, upload = _make_app_with_doc(client)
    doc_id = upload["documentId"]
    # all of these must look like "does not exist" to the other institution
    checks = [
        ("GET", f"/api/v1/applicant/applications/{app_id}", None),
        ("GET", f"/api/v1/applications/{app_id}/deficiencies", None),
        ("GET", f"/api/v1/documents/{doc_id}/file", None),
        (
            "POST",
            f"/api/v1/applications/{app_id}/documents",
            {"files": {"file": ("x.pdf", b"%PDF-1.4 x", "application/pdf")}, "data": {"requirement_code": "AFFIDAVIT"}},
        ),
        ("POST", f"/api/v1/applications/{app_id}/resubmit", {"json": {"note": "x"}}),
    ]
    for method, url, extra in checks:
        res = client.request(method, url, headers=other_applicant, **(extra or {}))
        assert res.status_code == 404, f"{method} {url} -> {res.status_code} {res.text[:120]}"

    mine = client.get(f"/api/v1/applicant/applications/{app_id}", headers=auth_headers("applicant"))
    assert mine.status_code == 200


def test_applicant_upload_response_hides_internal_results(client):
    _, upload = _make_app_with_doc(client)
    assert upload["findings"] == []
    checks = upload["fileChecks"]
    assert set(checks) <= {"ok", "errors", "warnings", "extension", "size_bytes"}
    assert "sha256" not in checks and "checks" not in checks

    # Staff still see the full picture for the same application.
    detail = client.get("/api/v1/applications", headers=auth_headers("officer"))
    assert detail.status_code == 200


def test_applicant_application_view_has_no_internal_fields(client):
    app_id, _ = _make_app_with_doc(client)
    body = client.get(
        f"/api/v1/applicant/applications/{app_id}", headers=auth_headers("applicant")
    ).json()
    flat = str(body).lower()
    for forbidden in ("riskscore", "risk_score", "priorityscore", "sha256", "extractedfields", "forensic"):
        assert forbidden not in flat, f"applicant view leaks {forbidden}"


def test_applicant_create_response_is_the_narrow_view(client):
    created = client.post(
        "/api/v1/applications",
        headers=auth_headers("applicant"),
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Narrow View Institute",
            "program_name": "B.Tech",
            "academic_year": "2025-26",
        },
    ).json()
    assert {"id", "applicationNumber", "status", "requirements", "deficiencies"} <= set(created)
    flat = str(created).lower()
    for forbidden in ("priorityscore", "scorebreakdown", "extractedfields", "riskscore"):
        assert forbidden not in flat, f"create response leaks {forbidden}"
