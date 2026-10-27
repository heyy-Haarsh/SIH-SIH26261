"""P1 scrutiny workflow regressions.

Covers: current-run findings (no duplicate/stale issues), resolution carry-forward rules, grouped
plain-language review, handbook reference honesty, per-document pipeline, file preview access,
cross-document reconciliation updating when documents change, decision context and PDF report.
"""

from __future__ import annotations

import json

import fitz  # PyMuPDF — used only to read the generated PDF back

from tests.conftest import auth_headers

APPLICANT = auth_headers("applicant")
OFFICER = auth_headers("officer")
ADMIN = auth_headers("admin")


def _create(client):
    res = client.post(
        "/api/v1/applications",
        headers=APPLICANT,
        json={
            "category_code": "NEW-ENG",
            "institution_name": "Shivaji Institute of Technology",
            "program_name": "B.Tech CSE",
            "academic_year": "2025-26",
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


def _upload(client, app_id, req, body: bytes, name="doc.txt"):
    res = client.post(
        f"/api/v1/applications/{app_id}/documents",
        headers=APPLICANT,
        files={"file": (name, body, "text/plain")},
        data={"requirement_code": req},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _review(client, app_id):
    res = client.get(f"/api/v1/applications/{app_id}/scrutiny-review", headers=OFFICER)
    assert res.status_code == 200, res.text
    return res.json()


def _detail(client, app_id, headers=OFFICER):
    res = client.get(f"/api/v1/applications/{app_id}", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _revalidate(client, app_id):
    res = client.post(f"/api/v1/applications/{app_id}/validation-runs", headers=OFFICER)
    assert res.status_code == 200, res.text


def _all_issues(review):
    return [i for g in review["issueGroups"] for i in g["issues"]]


def _doc_id(client, app_id, req):
    detail = _detail(client, app_id)
    return next(d["id"] for d in detail["documents"] if d["requirementCode"] == req)


def _mismatch_app(client):
    app_id = _create(client)
    _upload(client, app_id, "AFFIDAVIT", b"Institution Name: Alpha College\n", "a.txt")
    _upload(client, app_id, "LAND_OWNERSHIP", b"Institution Name: Beta College\n", "b.txt")
    return app_id


# ---- current findings vs history ----------------------------------------------------------


def test_repeated_validation_does_not_duplicate_current_findings(client):
    app_id = _mismatch_app(client)
    before = _detail(client, app_id)
    n = len(before["findings"])
    assert n > 0
    for _ in range(3):
        _revalidate(client, app_id)
    after = _detail(client, app_id)
    assert len(after["findings"]) == n
    # The headline count is the review's own open-issue count, never the raw finding rows.
    assert after["findingCount"] == _review(client, app_id)["openIssueCount"]
    ids_after = [f["id"] for f in after["findings"]]
    assert len(ids_after) == len(set(ids_after))
    assert not {f["id"] for f in before["findings"]} & set(ids_after), "stale run findings shown"
    review = _review(client, app_id)
    assert review["historicalFindingCount"] >= n  # old runs are kept as history


def test_resolution_carries_over_only_for_the_same_document_version(client):
    app_id = _create(client)
    _upload(client, app_id, "AFFIDAVIT", b"Institution Name: Alpha College\n", "expired_affidavit.txt")
    client.post(f"/api/v1/applications/{app_id}/scrutiny/start", headers=OFFICER)
    detail = _detail(client, app_id)
    target = next(f for f in detail["findings"] if "expired" in f["title"].lower())
    res = client.post(
        f"/api/v1/findings/{target['id']}/resolve",
        headers=OFFICER,
        json={"status": "accepted", "reason": "Officer saw the original; it is current."},
    )
    assert res.status_code == 200, res.text

    _revalidate(client, app_id)  # same file -> resolution is kept
    again = next(f for f in _detail(client, app_id)["findings"] if "expired" in f["title"].lower())
    assert again["status"] == "accepted"

    # the applicant replaces the file: the old resolution must not hide the new file's issue
    _upload(client, app_id, "AFFIDAVIT", b"Institution Name: Alpha College v2\n", "expired_affidavit.txt")
    reopened = next(f for f in _detail(client, app_id)["findings"] if "expired" in f["title"].lower())
    assert reopened["status"] == "open"


def test_replaced_document_fields_are_not_mixed_with_current_ones(client):
    app_id = _create(client)
    _upload(client, app_id, "AFFIDAVIT", b"Institution Name: Old College\n", "a.txt")
    _upload(client, app_id, "AFFIDAVIT", b"Institution Name: New College\n", "a2.txt")
    fields = _detail(client, app_id)["extractedFields"]
    values = {f["value"] for f in fields if f["fieldName"] == "institution_name"}
    assert values == {"New College"}


# ---- reconciliation updates when documents change ----------------------------------------------


def test_cross_document_mismatch_clears_after_the_document_is_corrected(client):
    app_id = _mismatch_app(client)
    review = _review(client, app_id)
    cross = [g for g in review["issueGroups"] if g["scope"] == "cross_document"]
    assert cross, "mismatching institution names must surface as a cross-document issue"
    issue = cross[0]["issues"][0]
    assert {d["name"] for d in issue["relatedDocuments"]} >= {"Land Ownership / Lease Deed"} or issue[
        "relatedDocuments"
    ]

    _upload(client, app_id, "LAND_OWNERSHIP", b"Institution Name: Alpha College\n\n\n", "b2.txt")
    fixed = _review(client, app_id)
    assert not [g for g in fixed["issueGroups"] if g["scope"] == "cross_document"]
    detail = _detail(client, app_id)
    assert not [d for d in detail["discrepancies"] if d["outcome"] != "MATCH"]


# ---- grouped, deduplicated, plain-language review ---------------------------------------------


def test_review_is_grouped_deduplicated_and_plain_language(client):
    app_id = _mismatch_app(client)
    _revalidate(client, app_id)
    review = _review(client, app_id)
    issues = _all_issues(review)
    assert issues
    keys = [i["key"] for i in issues]
    assert len(keys) == len(set(keys)), "duplicate issue keys"
    blob = json.dumps(review)
    assert "[SYNTHETIC]" not in blob
    assert "SYN-RULE" not in blob
    assert "TODO" not in blob
    assert "placeholder" not in blob.lower()
    # capability disclosure (SYN-RULE-008) is a limitation, not an issue
    assert not any("capabilities are unavailable" in i["title"].lower() for i in issues)
    assert review["limitations"]
    groups = [g["scope"] for g in review["issueGroups"]]
    assert "application" in groups  # missing mandatory documents
    for i in issues:
        assert i["title"] and i["explanation"]
        assert i["severity"] in {"failed", "manual_review", "warning", "info"}


def test_missing_documents_are_listed_and_have_an_applicant_action(client):
    app_id = _create(client)
    _upload(client, app_id, "AFFIDAVIT", b"Institution Name: Alpha College\n")
    review = _review(client, app_id)
    assert review["missingDocuments"]
    missing = [i for i in _all_issues(review) if i["title"].startswith("Required document not uploaded")]
    assert missing
    assert all(i["applicantAction"].startswith("Upload") for i in missing)


# ---- handbook references are never invented ------------------------------------------------------


def test_handbook_references_are_unverified_until_an_admin_verifies_them(client):
    app_id = _create(client)
    _upload(client, app_id, "AFFIDAVIT", b"Institution Name: Alpha College\n")
    review = _review(client, app_id)
    missing = next(i for i in _all_issues(review) if i["title"].startswith("Required document not uploaded"))
    assert missing["handbook"]["status"] == "unverified"
    assert missing["handbook"]["edition"] is None

    # incomplete reference cannot be marked verified
    bad = client.put(
        "/api/v1/admin/handbook-references",
        headers=ADMIN,
        json={"reference_key": "SYN-RULE-001", "edition": "2024-27", "section": "3.1", "verified": True},
    )
    assert bad.status_code == 422

    # only admins may edit references
    denied = client.put(
        "/api/v1/admin/handbook-references",
        headers=OFFICER,
        json={"reference_key": "SYN-RULE-001", "edition": "x", "section": "x", "page": "1", "verified": True},
    )
    assert denied.status_code == 403

    ok = client.put(
        "/api/v1/admin/handbook-references",
        headers=ADMIN,
        json={
            "reference_key": "SYN-RULE-001",
            "edition": "Test Edition",
            "section": "Test Section",
            "page": "99",
            "title": "Test clause",
            "verified": True,
        },
    )
    assert ok.status_code == 200, ok.text
    review2 = _review(client, app_id)
    missing2 = next(i for i in _all_issues(review2) if i["title"].startswith("Required document not uploaded"))
    assert missing2["handbook"] == {
        "status": "verified",
        "edition": "Test Edition",
        "section": "Test Section",
        "page": "99",
        "title": "Test clause",
        "note": "",
    }

    # an incomplete, unverified draft is shown as unverified, never as a citation
    client.put(
        "/api/v1/admin/handbook-references",
        headers=ADMIN,
        json={"reference_key": "SYN-RULE-001", "edition": "Test Edition", "verified": False},
    )
    review3 = _review(client, app_id)
    missing3 = next(i for i in _all_issues(review3) if i["title"].startswith("Required document not uploaded"))
    assert missing3["handbook"]["status"] == "unverified"


# ---- per-document pipeline & preview --------------------------------------------------------------


def test_document_report_shows_the_full_pipeline(client):
    app_id = _create(client)
    _upload(client, app_id, "AFFIDAVIT", b"Institution Name: Alpha College\n", "a.txt")
    doc_id = _doc_id(client, app_id, "AFFIDAVIT")
    res = client.get(f"/api/v1/applications/{app_id}/documents/{doc_id}/report", headers=OFFICER)
    assert res.status_code == 200, res.text
    rep = res.json()
    assert [s["key"] for s in rep["stages"]] == [
        "intake",
        "classification",
        "layer1",
        "layer2",
        "layer3",
    ]
    for s in rep["stages"]:
        assert s["status"] in {"pass", "warning", "failed", "manual_review", "unavailable", "not_run"}
        assert s["summary"]
    assert any(f["fieldName"] == "institution_name" for f in rep["extractedFields"])
    assert rep["versions"][0]["isCurrent"] is True
    assert "not prove" in rep["disclaimer"].lower() or "does not prove" in rep["disclaimer"].lower()

    _upload(client, app_id, "AFFIDAVIT", b"Institution Name: Alpha College 2\n", "a2.txt")
    rep2 = client.get(f"/api/v1/applications/{app_id}/documents/{doc_id}/report", headers=OFFICER).json()
    assert [v["version"] for v in rep2["versions"]] == [2, 1]
    assert rep2["document"]["fileName"] == "a2.txt"
    values = {f["value"] for f in rep2["extractedFields"] if f["fieldName"] == "institution_name"}
    assert values == {"Alpha College 2"}


def test_document_report_404_for_a_document_of_another_application(client):
    a = _create(client)
    b = _create(client)
    _upload(client, a, "AFFIDAVIT", b"Institution Name: Alpha College\n")
    doc_id = _doc_id(client, a, "AFFIDAVIT")
    res = client.get(f"/api/v1/applications/{b}/documents/{doc_id}/report", headers=OFFICER)
    assert res.status_code == 404


def test_document_file_preview_access(client):
    app_id = _create(client)
    _upload(client, app_id, "AFFIDAVIT", b"Institution Name: Alpha College\n", "a.txt")
    doc_id = _doc_id(client, app_id, "AFFIDAVIT")
    for headers in (OFFICER, APPLICANT, ADMIN):
        res = client.get(f"/api/v1/documents/{doc_id}/file", headers=headers)
        assert res.status_code == 200, headers
        assert res.content.startswith(b"Institution Name: Alpha College")
        assert res.headers["content-disposition"].startswith("inline")
        assert res.headers["x-content-type-options"] == "nosniff"
    assert client.get(f"/api/v1/documents/{doc_id}/file").status_code in (401, 403)
    assert client.get("/api/v1/documents/does-not-exist/file", headers=OFFICER).status_code == 404


# ---- RBAC for the review surface ------------------------------------------------------------------


def test_review_and_reports_are_not_available_to_applicants(client):
    app_id = _create(client)
    doc = _upload(client, app_id, "AFFIDAVIT", b"Institution Name: Alpha College\n")
    for path in (
        f"/api/v1/applications/{app_id}/scrutiny-review",
        f"/api/v1/applications/{app_id}/documents/{doc['documentId']}/report",
        f"/api/v1/applications/{app_id}/report.pdf",
        f"/api/v1/applications/{app_id}/report.json",
    ):
        res = client.get(path, headers=APPLICANT)
        assert res.status_code == 403, path


# ---- decision context ----------------------------------------------------------------------------


def test_review_explains_what_the_applicant_must_correct_and_keeps_decisions(client):
    app_id = _mismatch_app(client)
    review = _review(client, app_id)
    d = review["decision"]
    assert d["mustCorrect"], "open issues with an applicant action must be listed"
    assert d["mustCorrectRows"], "correction rows must name a document and an action"
    assert all(r.get("action") for r in d["mustCorrectRows"])
    assert d["clarificationDraftBody"].startswith("Please correct the following")
    assert d["rejectionDraftBody"].startswith("The application cannot be recommended")
    assert all(not line.startswith("None") for line in d["mustCorrect"])

    client.post(f"/api/v1/applications/{app_id}/scrutiny/start", headers=OFFICER)
    res = client.post(
        f"/api/v1/applications/{app_id}/scrutiny/decision",
        headers=OFFICER,
        json={"reason": "Names do not match and mandatory documents are missing.", "recommend": False},
    )
    assert res.status_code == 200, res.text
    after = _review(client, app_id)
    assert after["decision"]["finalDecision"] == "rejected"
    assert "Names do not match" in after["decision"]["finalDecisionReason"]
    mine = client.get(f"/api/v1/applicant/applications/{app_id}", headers=APPLICANT)
    assert mine.status_code == 200
    assert mine.json()["officerDecision"] == "rejected"
    assert mine.json()["officerDecisionReason"]

    _revalidate(client, app_id)  # re-running checks must not erase the recorded decision
    summary = _detail(client, app_id)["scrutinySummary"]
    assert summary["finalDecision"] == "rejected"
    assert "Names do not match" in summary["finalDecisionReason"]


# ---- PDF ---------------------------------------------------------------------------------------------


def test_pdf_report_is_a_real_formatted_pdf(client):
    app_id = _mismatch_app(client)
    res = client.get(f"/api/v1/applications/{app_id}/report.pdf", headers=OFFICER)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "attachment" in res.headers["content-disposition"]
    assert res.content[:4] == b"%PDF"

    pdf = fitz.open(stream=res.content, filetype="pdf")
    text = "\n".join(page.get_text() for page in pdf)
    assert pdf.page_count >= 2
    assert "Scrutiny Report" in text
    assert "Issues by document" in text
    assert "Verification pipeline per document" in text
    assert "Not verified" in text  # handbook references are never invented
    assert f"Page 1 of {pdf.page_count}" in text
    assert "[SYNTHETIC]" not in text and "SYN-RULE" not in text
    assert "Shivaji Institute of Technology" in text
