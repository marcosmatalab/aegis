"""Tests for the gateway health endpoint."""

from fastapi.testclient import TestClient

from aegis import __version__
from aegis.gateway.main import app

client = TestClient(app)


def test_health_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200

    body = resp.json()
    assert body["status"] == "ok"
    assert body["version"] == __version__
