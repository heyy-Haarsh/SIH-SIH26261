"""Phase 3: cross-document reconciliation tests."""

from tests.conftest import auth_headers


def _create_app(client):
    res = client.post(
        "/api/v1/applications",
        headers=auth_headers("applicant"),
        json={
            "category_code": "NEW-ENG",
            "program_name": "B.Tech Reconciliation",
            "academic_year": "2025-26",
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _upload(client, app_id: str, filename: str, body: bytes, requirement: str):
    res = client.post(
        f"/api/v1/applications/{app_id}/documents",
        headers=auth_headers("applicant"),
        files={"file": (filename, body, "text/plain")},
        data={"requirement_code": requirement},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_formatting_difference_is_match_after_normalization(client):
    app_id = _create_app(client)
    _upload(
        client,
        app_id,
        "affidavit.txt",
        b"Institution Name: Demo Institute of Technology\nRegistration Number: REG-001\n",
        "AFFIDAVIT",
    )
    _upload(
        client,
        app_id,
        "land.txt",
        b"Institution Name: demo institute of technology\nRegistration Number: reg 001\n",
        "LAND_OWNERSHIP",
    )

    run = client.post(
        f"/api/v1/applications/{app_id}/reconciliation-runs",
        headers=auth_headers("officer"),
    )
    assert run.status_code == 200, run.text
    items = run.json()["items"]
    inst = [i for i in items if i["fieldName"] == "institution_name"]
    assert inst, items
    assert inst[0]["outcome"] == "MATCH"
    assert inst[0]["matchKind"] == "normalization"

    reg = [i for i in items if i["fieldName"] == "registration_number"]
    assert reg
    assert reg[0]["outcome"] == "MATCH"


def test_conflicting_and_missing_values(client):
    app_id = _create_app(client)
    _upload(
        client,
        app_id,
        "a.txt",
        b"Institution Name: Alpha College\nSurvey Number: 12/3\nLand Area: 2.5 acres\n",
        "AFFIDAVIT",
    )
    _upload(
        client,
        app_id,
        "b.txt",
        b"Institution Name: Beta College\nAddress: 1 Main Road\n",
        "LAND_OWNERSHIP",
    )

    run = client.post(
        f"/api/v1/applications/{app_id}/reconciliation-runs",
        headers=auth_headers("officer"),
    )
    assert run.status_code == 200, run.text
    by_field = {i["fieldName"]: i for i in run.json()["items"]}
    assert by_field["institution_name"]["outcome"] == "MISMATCH"
    assert by_field["institution_name"]["outcome"] != "FRAUD"
    desc = by_field["institution_name"]["description"].lower()
    assert "not a fraud" in desc or "not labeled as fraud" in desc
    # Present on one doc only among multi-doc app → MISSING_DATA
    assert by_field["survey_number"]["outcome"] == "MISSING_DATA"
    assert by_field["address"]["outcome"] == "MISSING_DATA"

    # Application detail surfaces discrepancies
    detail = client.get(
        f"/api/v1/applications/{app_id}",
        headers=auth_headers("officer"),
    )
    assert detail.status_code == 200
    discs = detail.json()["discrepancies"]
    assert any(d["outcome"] == "MISMATCH" for d in discs)
    # Evidence links both documents
    mismatch = next(d for d in discs if d["fieldName"] == "institution_name")
    assert len(mismatch["values"]) >= 2
    assert all(v.get("documentId") for v in mismatch["values"])
    assert all(v.get("extractedFieldId") for v in mismatch["values"])


def test_possible_duplicate_documents(client):
    app_id = _create_app(client)
    body = b"Institution Name: Same Content College\nIssue Date: 01-01-2024\n"
    _upload(client, app_id, "copy_a.txt", body, "AFFIDAVIT")
    _upload(client, app_id, "copy_b.txt", body, "LAND_OWNERSHIP")

    run = client.post(
        f"/api/v1/applications/{app_id}/reconciliation-runs",
        headers=auth_headers("officer"),
    )
    assert run.status_code == 200, run.text
    dups = [i for i in run.json()["items"] if i["outcome"] == "POSSIBLE_DUPLICATE"]
    assert dups
    assert dups[0]["outcome"] == "POSSIBLE_DUPLICATE"
    assert "not labeled as fraud" in dups[0]["description"].lower()


def test_ambiguous_dates_manual_review(client):
    app_id = _create_app(client)
    _upload(
        client,
        app_id,
        "a.txt",
        b"Institution Name: Date College\nIssue Date: 01/02/2024\n",
        "AFFIDAVIT",
    )
    _upload(
        client,
        app_id,
        "b.txt",
        b"Institution Name: Date College\nIssue Date: circa early 2024\n",
        "AFFILIATION",
    )

    run = client.post(
        f"/api/v1/applications/{app_id}/reconciliation-runs",
        headers=auth_headers("officer"),
    )
    assert run.status_code == 200, run.text
    dates = [i for i in run.json()["items"] if i["fieldName"] == "issue_date"]
    assert dates
    assert dates[0]["outcome"] in {"MANUAL_REVIEW", "MISMATCH"}


def test_rerun_does_not_duplicate_open_findings(client):
    app_id = _create_app(client)
    _upload(
        client,
        app_id,
        "a.txt",
        b"Institution Name: Rerun College A\n",
        "AFFIDAVIT",
    )
    _upload(
        client,
        app_id,
        "b.txt",
        b"Institution Name: Rerun College B\n",
        "LAND_OWNERSHIP",
    )

    first = client.post(
        f"/api/v1/applications/{app_id}/reconciliation-runs",
        headers=auth_headers("officer"),
    )
    assert first.status_code == 200
    items1 = client.get(
        f"/api/v1/applications/{app_id}/reconciliation-items",
        headers=auth_headers("officer"),
    ).json()
    mismatch_ids = {i["id"] for i in items1 if i["outcome"] == "MISMATCH"}
    assert mismatch_ids

    second = client.post(
        f"/api/v1/applications/{app_id}/reconciliation-runs",
        headers=auth_headers("officer"),
    )
    assert second.status_code == 200
    assert second.json()["summary"]["reused"] >= 1
    items2 = client.get(
        f"/api/v1/applications/{app_id}/reconciliation-items",
        headers=auth_headers("officer"),
    ).json()
    mismatch_ids2 = {i["id"] for i in items2 if i["outcome"] == "MISMATCH"}
    assert mismatch_ids2 == mismatch_ids


def test_updated_document_clears_or_changes_conflict(client):
    app_id = _create_app(client)
    _upload(
        client,
        app_id,
        "a.txt",
        b"Institution Name: Update College\n",
        "AFFIDAVIT",
    )
    _upload(
        client,
        app_id,
        "b.txt",
        b"Institution Name: Different Name\n",
        "LAND_OWNERSHIP",
    )
    client.post(
        f"/api/v1/applications/{app_id}/reconciliation-runs",
        headers=auth_headers("officer"),
    )
    # Replace land doc with matching institution name (new version via re-upload)
    _upload(
        client,
        app_id,
        "b_fixed.txt",
        b"Institution Name: Update College\n",
        "LAND_OWNERSHIP",
    )
    again = client.post(
        f"/api/v1/applications/{app_id}/reconciliation-runs",
        headers=auth_headers("officer"),
    )
    assert again.status_code == 200
    open_items = client.get(
        f"/api/v1/applications/{app_id}/reconciliation-items",
        headers=auth_headers("officer"),
    ).json()
    open_mismatch = [
        i for i in open_items if i["fieldName"] == "institution_name" and i["outcome"] == "MISMATCH"
    ]
    assert open_mismatch == []
    matches = [
        i for i in open_items if i["fieldName"] == "institution_name" and i["outcome"] == "MATCH"
    ]
    assert matches


def test_officer_resolve_preserves_original_and_audits(client):
    app_id = _create_app(client)
    _upload(client, app_id, "a.txt", b"Institution Name: Resolve A\n", "AFFIDAVIT")
    _upload(client, app_id, "b.txt", b"Institution Name: Resolve B\n", "LAND_OWNERSHIP")
    client.post(
        f"/api/v1/applications/{app_id}/reconciliation-runs",
        headers=auth_headers("officer"),
    )
    items = client.get(
        f"/api/v1/applications/{app_id}/reconciliation-items",
        headers=auth_headers("officer"),
    ).json()
    item = next(i for i in items if i["outcome"] == "MISMATCH")

    resolved = client.post(
        f"/api/v1/reconciliation-items/{item['id']}/resolve",
        headers=auth_headers("officer"),
        json={"status": "waived", "reason": "Accepted abbreviation difference after review"},
    )
    assert resolved.status_code == 200, resolved.text
    body = resolved.json()
    assert body["status"] == "waived"
    assert body["originalOutcome"] == "MISMATCH"
    assert body["outcome"] == "MISMATCH"  # outcome preserved
    assert "abbreviation" in body["resolutionReason"]

    detail = client.get(
        f"/api/v1/applications/{app_id}",
        headers=auth_headers("officer"),
    ).json()
    assert any(
        "reconciliation.item_resolved" == a["action"] for a in detail["auditEvents"]
    )
    # Resolved item no longer in open list
    open_items = client.get(
        f"/api/v1/applications/{app_id}/reconciliation-items",
        headers=auth_headers("officer"),
    ).json()
    assert item["id"] not in {i["id"] for i in open_items}


def test_unauthorized_resolve_and_access(client):
    app_id = _create_app(client)
    _upload(client, app_id, "a.txt", b"Institution Name: Auth A\n", "AFFIDAVIT")
    _upload(client, app_id, "b.txt", b"Institution Name: Auth B\n", "LAND_OWNERSHIP")
    client.post(
        f"/api/v1/applications/{app_id}/reconciliation-runs",
        headers=auth_headers("officer"),
    )
    items = client.get(
        f"/api/v1/applications/{app_id}/reconciliation-items",
        headers=auth_headers("officer"),
    ).json()
    item_id = next(i["id"] for i in items if i["outcome"] == "MISMATCH")

    # Applicant cannot resolve
    denied = client.post(
        f"/api/v1/reconciliation-items/{item_id}/resolve",
        headers=auth_headers("applicant"),
        json={"status": "resolved", "reason": "Trying to resolve without officer role"},
    )
    assert denied.status_code in (401, 403)

    # Missing auth
    noauth = client.get(f"/api/v1/applications/{app_id}/reconciliation-runs/latest")
    assert noauth.status_code == 401


def test_validation_integrates_reconciliation(client):
    app_id = _create_app(client)
    _upload(client, app_id, "a.txt", b"Institution Name: Val A\n", "AFFIDAVIT")
    _upload(client, app_id, "b.txt", b"Institution Name: Val B\n", "LAND_OWNERSHIP")
    val = client.post(
        f"/api/v1/applications/{app_id}/validation-runs",
        headers=auth_headers("officer"),
    )
    assert val.status_code == 200, val.text
    latest = client.get(
        f"/api/v1/applications/{app_id}/reconciliation-runs/latest",
        headers=auth_headers("officer"),
    )
    assert latest.status_code == 200
    assert latest.json() is not None
    assert latest.json()["status"] == "completed"
    findings = val.json()["findings"]
    assert any(f.get("ruleId") == "SYN-RULE-007" or "cross-document" in (f.get("ruleName") or "").lower() or "differ" in f.get("title", "").lower() for f in findings)
