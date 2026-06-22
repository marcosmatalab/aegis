"""Integration tests for the real provider dependency wiring (no DI override).

These exercise ``get_provider -> build_provider(settings.default_provider)`` —
the seam the "switch by base_url only" promise rests on, which the
override-based fixtures in conftest deliberately bypass. Env vars take
precedence over any ``.env`` file, so these stay hermetic.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from aegis.gateway.config import get_settings
from aegis.gateway.main import app

_PAYLOAD = {"model": "mock/echo-1", "messages": [{"role": "user", "content": "hi"}]}


@pytest.fixture(autouse=True)
def _clean_state():
    app.dependency_overrides.clear()
    get_settings.cache_clear()
    yield
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_default_provider_wires_to_mock(monkeypatch):
    monkeypatch.setenv("AEGIS_DEFAULT_PROVIDER", "mock")
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        resp = test_client.post("/v1/chat/completions", json=_PAYLOAD)
    assert resp.status_code == 200
    assert resp.json()["id"].startswith("chatcmpl-")


def test_settings_drive_provider_selection(monkeypatch):
    # Proves the dependency actually reads settings.default_provider rather than
    # hardcoding a provider: selecting an unwired one yields the clean error.
    monkeypatch.setenv("AEGIS_DEFAULT_PROVIDER", "anthropic")
    get_settings.cache_clear()
    with TestClient(app) as test_client:
        resp = test_client.post("/v1/chat/completions", json=_PAYLOAD)
    assert resp.status_code == 500
    assert resp.json()["error"]["code"] == "provider_not_configured"
