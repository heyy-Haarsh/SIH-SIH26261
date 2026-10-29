"""Issuer registry — live authenticity verify against stored issuer records."""

from tests.conftest import auth_headers


def test_list_seeded_registry_records(client):
    res = client.get("/api/v1/issuer-registry/records", headers=auth_headers("officer"))
    assert res.status_code == 200, res.text
    records = res.json()["records"]
    certs = {r["certificateNumber"] for r in records}
    assert "FIRE-VERIFIED-001" in certs
    assert "FIRE-REVOKED-0001" in certs


def test_verify_authentic_fire_noc(client):
    res = client.post(
        "/api/v1/issuer-registry/verify",
        headers=auth_headers("officer"),
        json={
            "docType": "FIRE_NOC",
            "certificateNumber": "FIRE-VERIFIED-001",
            "holderName": "Demo Institute of Technology",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["authentic"] is True
    assert body["result"] == "authentic"
    assert body["endpoint"] == "/api/v1/issuer-registry/verify"
    assert body["request"]["method"] == "POST"
    assert body["checks"]["numberFound"] is True
    assert body["checks"]["notRevoked"] is True
    assert body["matchedRecord"]["certificateNumber"] == "FIRE-VERIFIED-001"


def test_verify_revoked(client):
    res = client.post(
        "/api/v1/issuer-registry/verify",
        headers=auth_headers("officer"),
        json={
            "docType": "FIRE_NOC",
            "certificateNumber": "FIRE-REVOKED-0001",
            "holderName": "Demo Institute of Technology",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["authentic"] is False
    assert body["result"] == "revoked"


def test_verify_not_found(client):
    res = client.post(
        "/api/v1/issuer-registry/verify",
        headers=auth_headers("officer"),
        json={
            "docType": "FIRE_NOC",
            "certificateNumber": "FIRE-DOES-NOT-EXIST",
            "holderName": "Anyone",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["authentic"] is False
    assert body["result"] == "not_found"


def test_verify_requires_certificate_number(client):
    res = client.post(
        "/api/v1/issuer-registry/verify",
        headers=auth_headers("officer"),
        json={"docType": "FIRE_NOC", "holderName": "Demo"},
    )
    assert res.status_code == 422, res.text


def test_verify_events_officer_only(client):
    client.post(
        "/api/v1/issuer-registry/verify",
        headers=auth_headers("officer"),
        json={
            "docType": "FIRE_NOC",
            "certificateNumber": "FIRE-VERIFIED-001",
            "holderName": "Demo Institute of Technology",
        },
    )
    ok = client.get("/api/v1/issuer-registry/events", headers=auth_headers("officer"))
    assert ok.status_code == 200
    assert len(ok.json()["events"]) >= 1

    denied = client.get("/api/v1/issuer-registry/events", headers=auth_headers("applicant"))
    assert denied.status_code == 403
