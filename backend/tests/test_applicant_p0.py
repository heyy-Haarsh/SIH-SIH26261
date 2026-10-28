"""P0 applicant workflow regressions.

Covers: institution name capture, applicant view separation (no internal scrutiny data),
upload policy + Marathi OCR language handling, document-type / clarity checks, document
replacement versioning, and end-to-end resubmission guards.
"""

from __future__ import annotations

import json
from unittest.mock import patch

from app.document_processing import ocr_processor
from app.document_processing.semantic_classifier import is_category_mismatch
from app.models.enums import SemanticDocumentCategory
from tests.conftest import auth_headers

APPLICANT = auth_headers("applicant")
OFFICER = auth_headers("officer")

FORBIDDEN_KEYS = {
    "extractedFields",
    "priorityScore",
    "scoreBreakdown",
    "scrutinySummary",
    "forensicsIndicators",
    "forensicsLimitations",
    "findings",
    "discrepancies",
    "documentVerificationRuns",
    "verifications",
    "reviewNotes",
    "auditEvents",
    "requiresManualReview",
    "findingCount",
    "assignedOfficer",
    "ruleValidationStatus",
    "externalVerificationStatus",
    "latestVerificationRunId",
    "latestExtractionRunId",
    "ruleId",
    "handbookRef",
}


def _create(client, **overrides):
    body = {
        "category_code": "NEW-ENG",
        "institution_name": "Shivaji Institute of Technology",
        "program_name": "B.Tech CSE",
        "academic_year": "2025-26",
    }
    body.update(overrides)
    return client.post("/api/v1/applications", headers=APPLICANT, json=body)


def _upload(client, app_id, body: bytes, req: str, name="doc.txt"):
    return client.post(
        f"/api/v1/applications/{app_id}/documents",
        headers=APPLICANT,
        files={"file": (name, body, "text/plain")},
        data={"requirement_code": req},
    )


def _walk_keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _walk_keys(item)


def _applicant_view(client, app_id):
    res = client.get(f"/api/v1/applicant/applications/{app_id}", headers=APPLICANT)
    assert res.status_code == 200, res.text
    return res.json()


# ---- institution name -------------------------------------------------------------------


def test_institution_name_is_required_and_persisted(client):
    missing = client.post(
        "/api/v1/applications",
        headers=APPLICANT,
        json={"category_code": "NEW-ENG", "program_name": "X", "academic_year": "2025-26"},
    )
    assert missing.status_code == 422

    for bad in ("", "  ", "ab", "12345"):
        assert _create(client, institution_name=bad).status_code == 422, bad

    res = _create(client, institution_name="  Shivaji   Institute  of Technology ")
    assert res.status_code == 200, res.text
    assert res.json()["institutionName"] == "Shivaji Institute of Technology"

    listed = client.get("/api/v1/applications", headers=OFFICER).json()
    assert any(a["institutionName"] == "Shivaji Institute of Technology" for a in listed)
    view = _applicant_view(client, res.json()["id"])
    assert view["institutionName"] == "Shivaji Institute of Technology"


# ---- applicant view separation ----------------------------------------------------------


def test_applicant_view_has_no_internal_scrutiny_data(client):
    app = _create(client).json()
    _upload(client, app["id"], b"Affidavit. I solemnly affirm. Institution Name: Shivaji Institute", "AFFIDAVIT")
    view = _applicant_view(client, app["id"])

    leaked = FORBIDDEN_KEYS & set(_walk_keys(view))
    assert not leaked, f"applicant view leaks internal keys: {leaked}"
    text = json.dumps(view)
    assert "SYN-RULE" not in text
    assert "SIM-" not in text

    assert set(view) >= {"requirements", "deficiencies", "history", "status", "statusLabel"}
    row = next(r for r in view["requirements"] if r["code"] == "AFFIDAVIT")
    assert row["uploadStatus"] in {"uploaded", "needs_attention"}
    assert row["document"]["fileName"] == "doc.txt"


def test_applicant_view_is_applicant_only(client):
    app = _create(client).json()
    for role in ("officer", "regional_officer"):
        res = client.get(f"/api/v1/applicant/applications/{app['id']}", headers=auth_headers(role))
        assert res.status_code in (403, 404), role


def test_history_only_shows_applicant_relevant_events(client):
    app = _create(client).json()
    _upload(client, app["id"], b"Affidavit sworn deponent", "AFFIDAVIT")
    client.post(f"/api/v1/applications/{app['id']}/scrutiny/start", headers=OFFICER)
    client.post(
        f"/api/v1/applications/{app['id']}/scrutiny/note",
        headers=OFFICER,
        json={"content": "internal suspicion note"},
    )
    view = _applicant_view(client, app["id"])
    labels = {h["label"] for h in view["history"]}
    assert "Application created" in labels
    assert "Document uploaded" in labels
    text = json.dumps(view["history"])
    assert "internal suspicion note" not in text
    assert "validation" not in text.lower()


# ---- upload policy / OCR / Marathi -------------------------------------------------------


def test_upload_policy_matches_server_limits(client):
    res = client.get("/api/v1/applications/upload-policy", headers=APPLICANT)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["maxUploadBytes"] == body["maxUploadMb"] * 1024 * 1024
    assert {"pdf", "png", "jpg"} <= set(body["allowedExtensions"])
    assert "marathiSupported" in body


def _fake_pytesseract(langs: list[str]):
    class _Fake:
        class Output:
            DICT = "dict"

        @staticmethod
        def get_tesseract_version():
            return "5.3.0"

        @staticmethod
        def get_languages(config=""):
            return langs

    import sys
    import types

    mod = types.ModuleType("pytesseract")
    mod.get_tesseract_version = _Fake.get_tesseract_version
    mod.get_languages = _Fake.get_languages
    mod.TesseractNotFoundError = type("TesseractNotFoundError", (Exception,), {})
    sys.modules["pytesseract"] = mod
    return mod


def test_default_ocr_languages_include_marathi():
    from app.core.config import Settings

    assert Settings().ocr_language_list == ["eng", "hin", "mar"]


def test_ocr_degrades_instead_of_disabling_when_marathi_data_missing():
    import sys

    original = sys.modules.get("pytesseract")
    try:
        _fake_pytesseract(["eng", "osd"])
        status = ocr_processor.tesseract_status()
        assert status["available"] is True  # English OCR still works
        assert status["languages_usable"] == ["eng"]
        assert "mar" in status["languages_missing"]
        assert status["marathi_supported"] is False
        assert "Marathi" in status["message"] or "mar" in status["message"]

        _fake_pytesseract(["eng", "hin", "mar"])
        status = ocr_processor.tesseract_status()
        assert status["available"] is True
        assert status["marathi_supported"] is True
        assert status["languages_missing"] == []
    finally:
        if original is not None:
            sys.modules["pytesseract"] = original
        else:
            sys.modules.pop("pytesseract", None)


def test_marathi_affidavit_is_classified_as_affidavit(client):
    app = _create(client).json()
    marathi = "प्रतिज्ञापत्र\nमी शपथपूर्वक नमूद करतो की वरील माहिती खरी आहे.".encode("utf-8")
    res = _upload(client, app["id"], marathi, "AFFIDAVIT")
    assert res.status_code == 200, res.text
    check = res.json()["documentCheck"]
    assert check["typeMatch"] == "matched", check


# ---- document type match / clarity -------------------------------------------------------


def test_type_match_matched_mismatch_and_unclear(client):
    app = _create(client).json()

    ok = _upload(client, app["id"], b"AFFIDAVIT. I solemnly affirm as deponent. Sworn.", "AFFIDAVIT")
    assert ok.json()["documentCheck"]["typeMatch"] == "matched"
    assert ok.json()["documentCheck"]["clarity"] == "clear"

    wrong = _upload(
        client,
        app["id"],
        b"Fire Safety Certificate NOC issued by the fire department. Firefighting equipment inspected.",
        "AFFIDAVIT",
    )
    check = wrong.json()["documentCheck"]
    assert check["typeMatch"] == "mismatch"
    assert check["needsAttention"] is True
    assert "fire safety" in check["typeMatchMessage"].lower()

    vague = _upload(client, app["id"], b"hello there nothing useful", "LAND_OWNERSHIP", name="x.txt")
    assert vague.json()["documentCheck"]["typeMatch"] == "unclear"

    view = _applicant_view(client, app["id"])
    row = next(r for r in view["requirements"] if r["code"] == "AFFIDAVIT")
    assert row["uploadStatus"] == "needs_attention"
    assert row["document"]["documentCheck"]["typeMatch"] == "mismatch"


def test_compatible_categories_are_not_flagged_as_mismatch():
    # regression: CATEGORY_TO_REQUIREMENT existed but was never consulted
    assert not is_category_mismatch(SemanticDocumentCategory.TRUST_OR_SOCIETY, "AFFIDAVIT")
    assert not is_category_mismatch(SemanticDocumentCategory.TRUST_OR_SOCIETY, "LAND_OWNERSHIP")
    assert not is_category_mismatch(SemanticDocumentCategory.AFFIDAVIT, "AFFIDAVIT_2")
    assert is_category_mismatch(SemanticDocumentCategory.FIRE_NOC, "AFFIDAVIT")


# ---- replacement keeps versions ----------------------------------------------------------


def test_replacing_a_document_preserves_previous_version(client):
    app = _create(client).json()
    _upload(client, app["id"], b"Affidavit sworn deponent version one", "AFFIDAVIT", name="v1.txt")
    second = _upload(client, app["id"], b"Affidavit sworn deponent version two", "AFFIDAVIT", name="v2.txt")
    assert second.json()["documentVersion"] == 2
    assert second.json()["replacedPrevious"] is True

    row = next(
        r for r in _applicant_view(client, app["id"])["requirements"] if r["code"] == "AFFIDAVIT"
    )
    assert row["document"]["fileName"] == "v2.txt"
    assert row["document"]["version"] == 2
    assert [v["fileName"] for v in row["document"]["previousVersions"]] == ["v1.txt"]


def test_cannot_upload_after_final_decision(client):
    app = _create(client).json()
    client.post(f"/api/v1/applications/{app['id']}/scrutiny/start", headers=OFFICER)
    dec = client.post(
        f"/api/v1/applications/{app['id']}/scrutiny/decision",
        headers=OFFICER,
        json={"reason": "Does not meet the minimum requirements.", "recommend": False},
    )
    assert dec.status_code == 200, dec.text
    res = _upload(client, app["id"], b"Affidavit sworn", "AFFIDAVIT")
    assert res.status_code == 409
    view = _applicant_view(client, app["id"])
    assert view["canUpload"] is False
    rejection = next(h for h in view["history"] if h["label"].startswith("Rejected"))
    assert "minimum requirements" in rejection["detail"]


# ---- resubmission end to end -------------------------------------------------------------


def _request_clarification(client, app_id, title="Fix affidavit"):
    client.post(f"/api/v1/applications/{app_id}/scrutiny/start", headers=OFFICER)
    res = client.post(
        f"/api/v1/applications/{app_id}/scrutiny/clarification",
        headers=OFFICER,
        json={"title": title, "description": "Upload an affidavit with the matching name."},
    )
    assert res.status_code == 200, res.text


def test_resubmit_is_blocked_until_every_clarification_is_answered(client):
    app = _create(client).json()
    _upload(client, app["id"], b"Affidavit sworn deponent", "AFFIDAVIT")
    _request_clarification(client, app["id"])

    view = _applicant_view(client, app["id"])
    assert view["status"] == "clarification_required"
    assert view["canResubmit"] is False
    assert view["resubmitBlockers"]

    blocked = client.post(
        f"/api/v1/applications/{app['id']}/resubmit", headers=APPLICANT, json={"note": "done"}
    )
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "open_clarifications"
    assert blocked.json()["blockers"]
    # nothing changed
    assert _applicant_view(client, app["id"])["status"] == "clarification_required"


def test_resubmit_end_to_end_updates_status_reprocesses_and_persists(client):
    app = _create(client).json()
    app_id = app["id"]
    _upload(client, app_id, b"Affidavit sworn deponent v1", "AFFIDAVIT", name="old.txt")
    _request_clarification(client, app_id)

    notice = _applicant_view(client, app_id)["deficiencies"][0]
    assert notice["status"] == "open"
    resp = client.post(
        f"/api/v1/deficiencies/{notice['id']}/respond",
        headers=APPLICANT,
        json={"response": "Replaced the affidavit with the corrected one."},
    )
    assert resp.status_code == 200, resp.text
    _upload(client, app_id, b"Affidavit sworn deponent v2 corrected", "AFFIDAVIT", name="new.txt")

    view = _applicant_view(client, app_id)
    assert view["canResubmit"] is True

    res = client.post(
        f"/api/v1/applications/{app_id}/resubmit",
        headers=APPLICANT,
        json={"note": "Corrected affidavit uploaded."},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    # resubmit returns the applicant view, never internal scrutiny detail
    assert not (FORBIDDEN_KEYS & set(_walk_keys(body)))
    assert body["status"] in {"under_scrutiny", "resubmitted"}  # never stuck in 'processing'
    assert body["status"] != "clarification_required"

    # persistence: response stored, notice closed, history records the resubmission + note
    stored = body["deficiencies"][0]
    assert stored["status"] == "closed"
    assert stored["applicantResponse"] == "Replaced the affidavit with the corrected one."
    resub = next(h for h in body["history"] if h["label"] == "Application resubmitted")
    assert resub["detail"] == "Corrected affidavit uploaded."

    # reprocessing happened: officer sees a fresh validation run and both document versions kept
    officer_view = client.get(f"/api/v1/applications/{app_id}", headers=OFFICER).json()
    assert officer_view["validationRunId"]
    assert officer_view["status"] == body["status"]
    row = next(r for r in body["requirements"] if r["code"] == "AFFIDAVIT")
    assert row["document"]["fileName"] == "new.txt"
    assert [v["fileName"] for v in row["document"]["previousVersions"]] == ["old.txt"]


def test_resubmit_rejected_when_not_in_clarification(client):
    app = _create(client).json()
    res = client.post(
        f"/api/v1/applications/{app['id']}/resubmit", headers=APPLICANT, json={"note": "hi"}
    )
    assert res.status_code == 422


def test_resubmit_note_length_is_validated(client):
    app = _create(client).json()
    _request_clarification(client, app["id"])
    notice = _applicant_view(client, app["id"])["deficiencies"][0]
    client.post(
        f"/api/v1/deficiencies/{notice['id']}/respond",
        headers=APPLICANT,
        json={"response": "Handled the request as asked."},
    )
    res = client.post(
        f"/api/v1/applications/{app['id']}/resubmit",
        headers=APPLICANT,
        json={"note": "x" * 2001},
    )
    assert res.status_code == 422


# ---- existing databases get the new column ------------------------------------------------


def test_additive_column_upgrade_for_pre_existing_database(tmp_path):
    from sqlalchemy import create_engine, inspect, text

    from app.core.database import ensure_additive_columns

    eng = create_engine(f"sqlite:///{(tmp_path / 'old.db').as_posix()}")
    with eng.begin() as conn:
        # shape of the table before institution_name existed
        conn.execute(text("CREATE TABLE applications (id VARCHAR(36) PRIMARY KEY, program_name TEXT)"))
        conn.execute(text("INSERT INTO applications (id, program_name) VALUES ('a', 'B.Tech')"))

    ensure_additive_columns(eng)
    ensure_additive_columns(eng)  # idempotent

    assert "institution_name" in {c["name"] for c in inspect(eng).get_columns("applications")}
    with eng.connect() as conn:
        assert conn.execute(text("SELECT institution_name FROM applications")).scalar() == ""
