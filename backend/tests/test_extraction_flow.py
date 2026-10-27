from tests.conftest import auth_headers


def test_upload_txt_triggers_extraction_and_fields(client):
    create = client.post(
        "/api/v1/applications",
        headers=auth_headers("applicant"),
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Test Institute of Technology",
            "program_name": "B.Tech Demo",
            "academic_year": "2025-26",
        },
    )
    assert create.status_code == 200, create.text
    app_id = create.json()["id"]

    body = (
        b"Institution Name: Demo Institute of Technology\n"
        b"Issuing Authority: Demo State University\n"
        b"Registration Number: 00099\n"
        b"Issue Date: 10-01-2024\n"
        b"Valid Until: 10-01-2026\n"
    )
    upload = client.post(
        f"/api/v1/applications/{app_id}/documents",
        headers=auth_headers("applicant"),
        files={"file": ("affidavit.txt", body, "text/plain")},
        data={"requirement_code": "AFFIDAVIT"},
    )
    assert upload.status_code == 200, upload.text
    payload = upload.json()
    assert payload["documentId"]
    assert payload.get("extractionRunId")
    assert payload.get("extractionStatus") in {
        "completed",
        "completed_with_warnings",
        "requires_manual_review",
        "ocr_unavailable",
        "failed",
        "unsupported",
    }

    # Fetch extraction run
    run = client.get(
        f"/api/v1/documents/{payload['documentId']}/extraction-runs/latest",
        headers=auth_headers("officer"),
    )
    assert run.status_code == 200, run.text
    data = run.json()
    assert data["id"] == payload["extractionRunId"]
    names = {f["fieldName"] for f in data["fields"]}
    assert "institution_name" in names
    # Leading zeros preserved
    reg = next(f for f in data["fields"] if f["fieldName"] == "registration_number")
    assert reg["rawValue"] == "00099"

    # Idempotent re-run
    again = client.post(
        f"/api/v1/documents/{payload['documentId']}/extraction-runs",
        headers=auth_headers("officer"),
        json={"force": False, "run_validation_after": False},
    )
    assert again.status_code == 200
    assert again.json()["id"] == data["id"]


def test_unauthorized_document_extraction(client):
    # Create as applicant
    create = client.post(
        "/api/v1/applications",
        headers=auth_headers("applicant"),
        json={"category_code": "EOA", "institution_name": "Test Institute of Technology", "program_name": "X", "academic_year": "2025-26"},
    )
    app_id = create.json()["id"]
    upload = client.post(
        f"/api/v1/applications/{app_id}/documents",
        headers=auth_headers("applicant"),
        files={"file": ("note.txt", b"Institution Name: X\n", "text/plain")},
        data={"requirement_code": "AFFIDAVIT"},
    )
    doc_id = upload.json()["documentId"]

    # Fake document id
    res = client.get(
        "/api/v1/documents/does-not-exist/extraction-runs/latest",
        headers=auth_headers("officer"),
    )
    assert res.status_code == 404

    # Officer can access
    ok = client.get(
        f"/api/v1/documents/{doc_id}/extraction-runs/latest",
        headers=auth_headers("officer"),
    )
    assert ok.status_code == 200


def test_ocr_capability_endpoint(client):
    res = client.get("/api/v1/extraction/ocr-capability", headers=auth_headers("admin"))
    assert res.status_code == 200
    body = res.json()
    assert "available" in body
    assert "message" in body
