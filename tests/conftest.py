"""Shared fixtures and helpers for the F1 gateway test suite (offline, no keys)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from aegis.gateway.config import Settings
from aegis.gateway.main import app
from aegis.gateway.proxy import get_provider
from aegis.gateway.upstream import MockProvider
from aegis.guardrails import build_pipeline, get_guardrail_pipeline


@pytest.fixture
def client():
    """TestClient with the deterministic mock provider injected via DI override.

    Guardrails are not overridden, so they use real settings (master off by
    default) — i.e. this fixture exercises the F1-identical passthrough path.
    Overrides are cleared after each test so swaps never leak.
    """
    app.dependency_overrides[get_provider] = lambda: MockProvider()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


class RecordingProvider(MockProvider):
    """MockProvider that records the (possibly redacted) request it received, so
    tests can assert what actually reached the provider after input guardrails."""

    def __init__(self):
        self.last_request = None

    async def complete(self, request):
        self.last_request = request
        return await super().complete(request)

    async def stream(self, request):
        self.last_request = request
        async for chunk in super().stream(request):
            yield chunk


@pytest.fixture
def recording_provider():
    return RecordingProvider()


@pytest.fixture
def guarded_client(recording_provider):
    """Factory: ``guarded_client(**setting_overrides)`` -> TestClient with the
    guardrail pipeline enabled (master on by default) and the recording provider
    injected. Overrides cleared on teardown."""

    def _make(**overrides):
        opts = {"guardrails_enabled": True}
        opts.update(overrides)
        settings = Settings(_env_file=None, **opts)
        app.dependency_overrides[get_provider] = lambda: recording_provider
        app.dependency_overrides[get_guardrail_pipeline] = lambda: build_pipeline(settings)
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()


@pytest.fixture
def chat_payload():
    """Factory for a minimal valid OpenAI request body, with overrides."""

    def _make(**overrides):
        body = {"model": "mock/echo-1", "messages": [{"role": "user", "content": "ping"}]}
        body.update(overrides)
        return body

    return _make


@pytest.fixture
def parse_sse():
    """Parse an SSE response body into payloads (json dicts + literal '[DONE]')."""

    def _parse(resp):
        out = []
        for frame in resp.text.split("\n\n"):
            frame = frame.strip()
            if not frame:
                continue
            assert frame.startswith("data: "), f"bad SSE frame: {frame!r}"
            data = frame[len("data: ") :]
            out.append(data if data == "[DONE]" else json.loads(data))
        return out

    return _parse
