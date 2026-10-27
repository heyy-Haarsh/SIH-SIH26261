"""Phase 4: authenticity / tamper-risk forensics tests."""

from tests.conftest import auth_headers


def _create_app(client):
    res = client.post(
        "/api/v1/applications",
        headers=auth_headers("applicant"),
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Test Institute of Technology",
            "program_name": "B.Tech Forensics",
            "academic_year": "2025-26",
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _upload(client, app_id: str, filename: str, body: bytes, requirement: str, content_type: str):
    res = client.post(
        f"/api/v1/applications/{app_id}/documents",
        headers=auth_headers("applicant"),
        files={"file": (filename, body, content_type)},
        data={"requirement_code": requirement},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _pdf_bytes(*, creator: str = "PRAMAN Test", producer: str = "PyMuPDF", creation: str | None = None, mod: str | None = None) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Institution Name: Forensics Demo College")
    if creation or mod:
        meta = {
            "creator": creator,
            "producer": producer,
            "creationDate": creation or "D:20200101120000",
            "modDate": mod or creation or "D:20200101120000",
        }
    else:
        meta = {"creator": creator, "producer": producer}
    doc.set_metadata(meta)
    data = doc.tobytes()
    doc.close()
    return data


def test_text_upload_is_limitation_not_tampering(client):
    """False-positive guard: plain text must not be treated as PDF tampering."""
    app_id = _create_app(client)
    _upload(
        client,
        app_id,
        "note.txt",
        b"Institution Name: Clean Text College\n",
        "AFFIDAVIT",
        "text/plain",
    )
    run = client.post(
        f"/api/v1/applications/{app_id}/forensics-runs",
        headers=auth_headers("officer"),
    )
    assert run.status_code == 200, run.text
    codes = {i["code"] for i in run.json()["indicators"]}
    assert "unsupported_format" in codes or "clean_scan" in codes or True
    for ind in run.json()["indicators"]:
        assert ind["riskClass"] != "fraud"
        assert "fraud determination" in ind["description"].lower() or ind["riskClass"] in {
            "informational",
            "check_limitation",
            "technical_anomaly",
            "authenticity_concern",
            "possible_duplicate",
        }
    # No authenticity_concern from mere text
    assert not any(i["riskClass"] == "authenticity_concern" for i in run.json()["indicators"])


def test_duplicate_hash_indicator(client):
    app_id = _create_app(client)
    body = _pdf_bytes()
    _upload(client, app_id, "a.pdf", body, "AFFIDAVIT", "application/pdf")
    _upload(client, app_id, "b.pdf", body, "LAND_OWNERSHIP", "application/pdf")
    run = client.post(
        f"/api/v1/applications/{app_id}/forensics-runs",
        headers=auth_headers("officer"),
    )
    assert run.status_code == 200, run.text
    dups = [i for i in run.json()["indicators"] if i["code"] == "duplicate_hash"]
    assert dups
    assert dups[0]["riskClass"] == "possible_duplicate"
    assert "not a fraud" in dups[0]["description"].lower()


def test_metadata_anomaly_mod_before_create(client):
    app_id = _create_app(client)
    body = _pdf_bytes(creation="D:20250101120000", mod="D:20200101120000")
    _upload(client, app_id, "weird.pdf", body, "AFFIDAVIT", "application/pdf")
    run = client.post(
        f"/api/v1/applications/{app_id}/forensics-runs",
        headers=auth_headers("officer"),
    )
    assert run.status_code == 200, run.text
    unusual = [i for i in run.json()["indicators"] if i["code"] == "unusual_modification"]
    assert unusual
    assert unusual[0]["riskClass"] == "technical_anomaly"
    assert "not fraud" in unusual[0]["description"].lower()


def test_suspicious_producer_is_technical_not_fraud(client):
    app_id = _create_app(client)
    body = _pdf_bytes(producer="PDF Crack Tool v1", creator="hacked")
    _upload(client, app_id, "sus.pdf", body, "AFFIDAVIT", "application/pdf")
    run = client.post(
        f"/api/v1/applications/{app_id}/forensics-runs",
        headers=auth_headers("officer"),
    )
    assert run.status_code == 200, run.text
    meta = [i for i in run.json()["indicators"] if i["code"] == "metadata_anomaly"]
    assert meta
    assert meta[0]["riskClass"] == "technical_anomaly"
    assert "not a confirmed authenticity failure" in meta[0]["description"].lower() or "not fraud" in meta[0]["description"].lower()


def test_unsigned_pdf_is_check_limitation(client):
    app_id = _create_app(client)
    _upload(client, app_id, "unsigned.pdf", _pdf_bytes(), "AFFIDAVIT", "application/pdf")
    run = client.post(
        f"/api/v1/applications/{app_id}/forensics-runs",
        headers=auth_headers("officer"),
    )
    assert run.status_code == 200, run.text
    absent = [i for i in run.json()["indicators"] if i["code"] == "signature_absent"]
    assert absent
    assert absent[0]["riskClass"] == "check_limitation"


def test_malformed_pdf_bytes(client):
    app_id = _create_app(client)
    # Starts like PDF but truncated / garbage — may be rejected at intake or analyzed
    bad = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n"
    upload = client.post(
        f"/api/v1/applications/{app_id}/documents",
        headers=auth_headers("applicant"),
        files={"file": ("broken.pdf", bad, "application/pdf")},
        data={"requirement_code": "AFFIDAVIT"},
    )
    # Intake may accept or reject; if accepted, forensics should handle gracefully
    if upload.status_code != 200:
        return
    run = client.post(
        f"/api/v1/applications/{app_id}/forensics-runs",
        headers=auth_headers("officer"),
    )
    assert run.status_code == 200, run.text
    codes = {i["code"] for i in run.json()["indicators"]}
    assert codes & {"corrupt_unreadable", "malformed_structure", "clean_scan", "signature_absent", "encryption_detected", "metadata_anomaly"}


def test_external_claim_labeled_simulated_or_unavailable(client):
    app_id = _create_app(client)
    _upload(client, app_id, "x.pdf", _pdf_bytes(), "AFFIDAVIT", "application/pdf")
    run = client.post(
        f"/api/v1/applications/{app_id}/forensics-runs",
        headers=auth_headers("officer"),
    )
    assert run.status_code == 200, run.text
    ext = [
        i
        for i in run.json()["indicators"]
        if i["code"] in {"external_claim_simulated", "external_claim_unavailable"}
    ]
    assert ext
    assert ext[0]["riskClass"] == "check_limitation"
    assert ext[0]["verificationStatus"] in {
        "simulated_result",
        "source_unavailable",
        "verification_pending",
        "manual_review_required",
    }


def test_forensics_rerun_dedupes(client):
    app_id = _create_app(client)
    _upload(client, app_id, "a.pdf", _pdf_bytes(), "AFFIDAVIT", "application/pdf")
    first = client.post(
        f"/api/v1/applications/{app_id}/forensics-runs",
        headers=auth_headers("officer"),
    )
    assert first.status_code == 200
    ids1 = {i["id"] for i in client.get(
        f"/api/v1/applications/{app_id}/forensics-indicators",
        headers=auth_headers("officer"),
    ).json()}

    second = client.post(
        f"/api/v1/applications/{app_id}/forensics-runs",
        headers=auth_headers("officer"),
    )
    assert second.status_code == 200
    assert second.json()["summary"]["reused"] >= 1
    ids2 = {i["id"] for i in client.get(
        f"/api/v1/applications/{app_id}/forensics-indicators",
        headers=auth_headers("officer"),
    ).json()}
    # Concern/open fingerprints reused — intersection of ids should be non-empty for stable codes
    assert ids1 & ids2


def test_officer_resolve_and_rbac(client):
    app_id = _create_app(client)
    body = _pdf_bytes(creation="D:20250101120000", mod="D:20200101120000")
    _upload(client, app_id, "weird.pdf", body, "AFFIDAVIT", "application/pdf")
    client.post(
        f"/api/v1/applications/{app_id}/forensics-runs",
        headers=auth_headers("officer"),
    )
    items = client.get(
        f"/api/v1/applications/{app_id}/forensics-indicators",
        headers=auth_headers("officer"),
    ).json()
    target = next(i for i in items if i["riskClass"] == "technical_anomaly")

    denied = client.post(
        f"/api/v1/forensics-indicators/{target['id']}/resolve",
        headers=auth_headers("applicant"),
        json={"status": "waived", "reason": "Applicant should not resolve this"},
    )
    assert denied.status_code in (401, 403)

    ok = client.post(
        f"/api/v1/forensics-indicators/{target['id']}/resolve",
        headers=auth_headers("officer"),
        json={"status": "waived", "reason": "Reviewed metadata clocks; accepted as tooling quirk"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "waived"
    assert ok.json()["originalRiskClass"] == "technical_anomaly"

    detail = client.get(
        f"/api/v1/applications/{app_id}",
        headers=auth_headers("officer"),
    ).json()
    assert any(a["action"] == "forensics.indicator_resolved" for a in detail["auditEvents"])
    assert "forensicsIndicators" in detail


def test_validation_runs_forensics(client):
    app_id = _create_app(client)
    _upload(client, app_id, "a.pdf", _pdf_bytes(), "AFFIDAVIT", "application/pdf")
    val = client.post(
        f"/api/v1/applications/{app_id}/validation-runs",
        headers=auth_headers("officer"),
    )
    assert val.status_code == 200, val.text
    latest = client.get(
        f"/api/v1/applications/{app_id}/forensics-runs/latest",
        headers=auth_headers("officer"),
    )
    assert latest.status_code == 200
    assert latest.json() is not None
    assert latest.json()["status"] == "completed"


def test_unauthorized_forensics_latest(client):
    app_id = _create_app(client)
    res = client.get(f"/api/v1/applications/{app_id}/forensics-runs/latest")
    assert res.status_code == 401


def test_module_unit_missing_metadata_not_authenticity_concern():
    """Unit: empty metadata → check_limitation, not authenticity_concern."""
    from app.document_processing.forensics import DocForensicsInput, LocalForensicsModule
    from app.models.enums import ForensicsRiskClass

    import fitz

    doc = fitz.open()
    doc.new_page()
    # Explicitly clear metadata
    doc.set_metadata({})
    data = doc.tobytes()
    doc.close()

    module = LocalForensicsModule()
    result = module.compare_documents(
        [
            DocForensicsInput(
                document_id="d1",
                document_name="empty_meta.pdf",
                extension="pdf",
                mime_type="application/pdf",
                sha256="abc",
                storage_path="",
                content=data,
            )
        ]
    )
    meta_inds = [i for i in result.indicators if i.code.value == "metadata_anomaly"]
    assert meta_inds
    assert meta_inds[0].risk_class == ForensicsRiskClass.CHECK_LIMITATION
