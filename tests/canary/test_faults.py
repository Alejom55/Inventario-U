from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import faults


def build(monkeypatch, track="canary", enabled="true"):
    monkeypatch.setattr(faults, "TRACK", track)
    monkeypatch.setenv("FAULT_INJECTION_ENABLED", enabled)
    monkeypatch.setenv("TEAM_API_KEY", "secret")
    api = FastAPI()

    @api.get("/api/v3/skus")
    def skus():
        return []

    faults.install_faults(api)
    return TestClient(api)


def test_fault_requires_key_and_never_changes_stable(monkeypatch):
    client = build(monkeypatch)
    assert client.post("/api/v3/admin/fault", json={"error_rate": 1}).status_code == 401
    headers = {"X-Api-Key": "secret"}
    assert client.post("/api/v3/admin/fault", headers=headers, json={"error_rate": 1}).status_code == 200
    assert client.get("/api/v3/skus", headers=headers).status_code == 500
    assert client.get("/api/v3/skus").status_code == 200
    assert client.post("/api/v3/admin/fault", headers=headers, json={}).status_code == 200
    assert client.get("/api/v3/skus", headers=headers).status_code == 200
    for track, enabled in [("stable", "true"), ("canary", "false")]:
        client = build(monkeypatch, track, enabled)
        assert client.post("/api/v3/admin/fault", headers=headers, json={}).status_code == 404


def test_fault_rejects_unbounded_degradation(monkeypatch):
    client = build(monkeypatch)
    for payload in [{"error_rate": 2}, {"latency_ms": 2001}, {"latency_ms": -1}]:
        assert client.post("/api/v3/admin/fault", headers={"X-Api-Key": "secret"}, json=payload).status_code == 422
