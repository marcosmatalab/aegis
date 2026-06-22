"""Shared fixtures and helpers for the F1 gateway test suite (offline, no keys)."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from aegis.gateway.main import app
from aegis.gateway.proxy import get_provider
from aegis.gateway.upstream import MockProvider


@pytest.fixture
def client():
    """TestClient with the deterministic mock provider injected via DI override.

    Overrides are cleared after each test so provider swaps never leak.
    """
    app.dependency_overrides[get_provider] = lambda: MockProvider()
    with TestClient(app) as test_client:
        yield test_client
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
