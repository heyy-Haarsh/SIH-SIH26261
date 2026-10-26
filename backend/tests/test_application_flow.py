from tests.conftest import auth_headers


def test_create_upload_validate_flow(client):
    # Applicant creates application
    create = client.post(
        "/api/v1/applications",
        headers=auth_headers("applicant"),
        json={
            "category_code": "NEW-ENG",
            "program_name": "B.Tech — Demo Program",
            "academic_year": "2025-26",
        },
    )
    assert create.status_code == 200, create.text
    app = create.json()
    app_id = app["id"]
    assert app["applicationNumber"].startswith("PRM-")

    # Officer can view it
    detail = client.get(f"/api/v1/applications/{app_id}", headers=auth_headers("officer"))
    assert detail.status_code == 200

    # Upload a PDF-like file
    pdf_bytes = b"%PDF-1.4 demo content for praman tests\n"
    upload = client.post(
        f"/api/v1/applications/{app_id}/documents",
        headers=auth_headers("applicant"),
        files={"file": ("affidavit.pdf", pdf_bytes, "application/pdf")},
        data={"requirement_code": "AFFIDAVIT"},
    )
    assert upload.status_code == 200, upload.text
    payload = upload.json()
    assert payload["documentId"]
    assert payload["validationRunId"]
    assert payload["fileChecks"]["ok"] is True
    assert isinstance(payload["findings"], list)

    # Explicit validation run
    run = client.post(
        f"/api/v1/applications/{app_id}/validation-runs",
        headers=auth_headers("officer"),
    )
    assert run.status_code == 200
    assert run.json()["status"] == "completed"


def test_reject_disallowed_extension(client):
    create = client.post(
        "/api/v1/applications",
        headers=auth_headers("applicant"),
        json={
            "category_code": "EOA",
            "program_name": "Demo",
            "academic_year": "2025-26",
        },
    )
    app_id = create.json()["id"]
    upload = client.post(
        f"/api/v1/applications/{app_id}/documents",
        headers=auth_headers("applicant"),
        files={"file": ("malware.exe", b"MZ", "application/octet-stream")},
        data={"requirement_code": "AFFIDAVIT"},
    )
    assert upload.status_code in (400, 415)
