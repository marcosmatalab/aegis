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


def test_concurrent_first_requests_share_one_cached_build(monkeypatch):
    # Concurrent first-requests must all share ONE build — the bug this phase fixes
    # was a per-request rebuild (no cache), which here would show as build_count==8.
    # Driven via ASGITransport + gather so the requests genuinely overlap.
    # HONESTY: with the current synchronous build there is no await inside the locked
    # critical section, so this asserts the CACHE holds under concurrency (catches a
    # no-cache regression); it does NOT distinguish locked from lockless. The asyncio
    # lock is a defensive guard for a future await-in-critical-section.
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


# --- lifespan shutdown ------------------------------------------------------ #
def test_shutdown_closes_cached_provider(monkeypatch):
    from fastapi.testclient import TestClient

    _counting_build(monkeypatch)
    monkeypatch.setenv("AEGIS_DEFAULT_PROVIDER", "mock")
    get_settings.cache_clear()
    with TestClient(app) as client:  # `with` runs lifespan startup + shutdown
        client.post("/v1/chat/completions", json=_PAYLOAD)
        provider = app.state.provider
        assert provider is not None
    # exiting the context ran lifespan shutdown -> the cached provider was closed
    assert provider.closed == 1
    assert app.state.provider is None


def test_cache_switch_closes_old_provider_and_rebuilds(monkeypatch):
    # When the configured provider name changes between requests, the cache must
    # close the OLD provider (so its client/pool is not leaked) and build the new
    # one — exercising the in-get_provider invalidation branch.
    from fastapi.testclient import TestClient

    calls = _counting_build(monkeypatch)
    monkeypatch.setenv("AEGIS_DEFAULT_PROVIDER", "mock")
    get_settings.cache_clear()
    with TestClient(app) as client:
        assert client.post("/v1/chat/completions", json=_PAYLOAD).status_code == 200
        first = app.state.provider
        assert first is not None and first.closed == 0
        # flip the configured provider -> next request closes `first` and rebuilds
        monkeypatch.setenv("AEGIS_DEFAULT_PROVIDER", "mockb")
        get_settings.cache_clear()
        assert client.post("/v1/chat/completions", json=_PAYLOAD).status_code == 200
        second = app.state.provider
    assert first.closed == 1  # old provider closed on the switch (no leak)
    assert second is not first  # a new provider was built
    assert calls == ["mock", "mockb"]  # one build per distinct configured name


def test_shutdown_without_a_built_provider_does_not_error(monkeypatch):
    # boot + shutdown with no /v1 traffic (only /health) must not raise on the
    # None-guard (app.state.provider stays None, nothing to close)
    from fastapi.testclient import TestClient

    monkeypatch.setenv("AEGIS_DEFAULT_PROVIDER", "mock")
    get_settings.cache_clear()
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
    assert app.state.provider is None
