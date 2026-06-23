"""Lifecycle tests for the real provider/client: built ONCE per app, reused
across requests, and closed on shutdown. All offline (mock/fakes, no key, no SDK,
no network). These deliberately do NOT use the conftest dependency override —
that bypasses get_provider and the cache being tested here."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from aegis.gateway.config import get_settings
from aegis.gateway.main import app
from aegis.gateway.upstream import MockProvider

_PAYLOAD = {"model": "mock/echo-1", "messages": [{"role": "user", "content": "hi"}]}


@pytest.fixture(autouse=True)
def _reset_app_state():
    """Each test starts from a clean cache and no leftover DI overrides, so the
    module-level ``app`` singleton cannot leak a provider between tests."""
    app.dependency_overrides.clear()
    app.state.provider = None
    app.state.provider_key = None
    app.state.provider_lock = None
    get_settings.cache_clear()
    yield
    app.dependency_overrides.clear()
    app.state.provider = None
    app.state.provider_key = None
    app.state.provider_lock = None
    get_settings.cache_clear()


class _CountingMockProvider(MockProvider):
    """Mock that records construction + aclose, to prove single-build and close."""

    instances: list = []

    def __init__(self):
        super().__init__()
        self.closed = 0
        _CountingMockProvider.instances.append(self)

    async def aclose(self):
        self.closed += 1
        await super().aclose()


def _counting_build(monkeypatch):
    """Patch the build seam get_provider uses with a construction counter."""
    calls: list[str] = []
    _CountingMockProvider.instances = []

    def _build(name, settings=None):
        calls.append(name)
        return _CountingMockProvider()

    monkeypatch.setattr("aegis.gateway.proxy.build_provider", _build)
    return calls


def test_provider_reused_via_testclient(monkeypatch):
    from fastapi.testclient import TestClient

    calls = _counting_build(monkeypatch)
    monkeypatch.setenv("AEGIS_DEFAULT_PROVIDER", "mock")
    get_settings.cache_clear()
    with TestClient(app) as client:
        r1 = client.post("/v1/chat/completions", json=_PAYLOAD)
        r2 = client.post("/v1/chat/completions", json=_PAYLOAD)
    assert r1.status_code == 200 and r2.status_code == 200
    assert calls == ["mock"]  # built once, reused on the second request


def test_anthropic_no_key_is_500_on_every_request(monkeypatch):
    # a failed build (anthropic + no key) must NOT be cached: every request re-raises
    from fastapi.testclient import TestClient

    monkeypatch.setenv("AEGIS_DEFAULT_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    with TestClient(app) as client:
        r1 = client.post("/v1/chat/completions", json=_PAYLOAD)
        r2 = client.post("/v1/chat/completions", json=_PAYLOAD)
    assert r1.status_code == 500 and r2.status_code == 500
    assert r1.json()["error"]["code"] == "provider_not_configured"
    assert r2.json()["error"]["code"] == "provider_not_configured"


def test_concurrent_first_requests_build_exactly_once(monkeypatch):
    # The synchronous TestClient serializes requests and would pass even without the
    # lock; drive the ASGI app concurrently so a lockless build race would show up
    # as build_count > 1.
    calls = _counting_build(monkeypatch)
    monkeypatch.setenv("AEGIS_DEFAULT_PROVIDER", "mock")
    get_settings.cache_clear()
    # ASGITransport runs no lifespan, so seed app.state explicitly (lock binds to
    # the run loop on first acquire).
    app.state.provider = None
    app.state.provider_key = None
    app.state.provider_lock = asyncio.Lock()

    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
            responses = await asyncio.gather(
                *(client.post("/v1/chat/completions", json=_PAYLOAD) for _ in range(8))
            )
        return responses

    responses = asyncio.run(_run())
    assert all(r.status_code == 200 for r in responses)
    assert calls == ["mock"]  # one build despite 8 concurrent first-requests
