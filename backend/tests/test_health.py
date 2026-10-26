def test_health_ok(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "ok"
    assert "sqlite" in body["database"].lower()
    assert body["demoAuth"] is True
