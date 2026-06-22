"""Malformed-input and provider-error handling -> OpenAI error envelope."""

from __future__ import annotations

import pytest

from aegis.gateway.main import app
from aegis.gateway.proxy import get_provider
from aegis.gateway.upstream import build_provider


def _assert_openai_error(resp, status=400):
    assert resp.status_code == status, resp.text
    err = resp.json()["error"]
    assert set(err) == {"message", "type", "param", "code"}
    return err


@pytest.mark.parametrize(
    "payload",
    [
        {"messages": [{"role": "user", "content": "hi"}]},  # missing model
        {"model": "mock/echo-1"},  # missing messages
        {"model": "mock/echo-1", "messages": []},  # empty messages
        {"model": "mock/echo-1", "messages": [{"role": "wizard", "content": "x"}]},  # bad role
        {"model": "mock/echo-1", "messages": [{"role": "user", "content": 123}]},  # content type
        {"model": "mock/echo-1", "messages": [{"role": "user"}]},  # user without content
        {
            "model": "mock/echo-1",
            "messages": [{"role": "user", "content": "hi"}],
            "stream": "maybe",
        },  # stream not coercible to bool
        {"model": "mock/echo-1", "messages": "nope"},  # messages not a list
    ],
)
def test_validation_errors_return_openai_envelope(client, payload):
    resp = client.post("/v1/chat/completions", json=payload)
    err = _assert_openai_error(resp, 400)
    assert err["type"] == "invalid_request_error"


def test_malformed_json_returns_json_envelope(client):
    resp = client.post(
        "/v1/chat/completions",
        content=b"{not json",
        headers={"content-type": "application/json"},
    )
    err = _assert_openai_error(resp, 400)
    assert err["param"] is None
    # error is JSON, not an SSE frame, even though a stream may have been requested
    assert resp.headers["content-type"].startswith("application/json")


def test_unconfigured_provider_renders_clean_error(client, chat_payload):
    # Swap in a provider selection that is valid config but unwired in F1.
    app.dependency_overrides[get_provider] = lambda: build_provider("anthropic")
    resp = client.post("/v1/chat/completions", json=chat_payload())
    err = _assert_openai_error(resp, 500)
    assert err["type"] == "api_error"
    assert err["code"] == "provider_not_configured"
    assert "Traceback" not in resp.text  # no internal leak
