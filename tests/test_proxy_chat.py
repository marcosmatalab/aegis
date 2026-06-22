"""Non-streaming POST /v1/chat/completions contract (OpenAI response shape)."""

from __future__ import annotations

from collections.abc import AsyncIterator

from aegis.gateway.errors import UpstreamProviderError
from aegis.gateway.main import app
from aegis.gateway.proxy import get_provider
from aegis.gateway.schemas import ChatCompletionChunk
from aegis.gateway.upstream import Provider


class _UpstreamFailingProvider(Provider):
    """complete() raises a mapped upstream error (e.g. a 429 rate limit)."""

    name = "failing"

    async def complete(self, request):
        raise UpstreamProviderError(
            "upstream rate limit exceeded (retry after 30s)",
            status_code=429,
            type="rate_limit_error",
            code="rate_limit_exceeded",
        )

    async def stream(self, request) -> AsyncIterator[ChatCompletionChunk]:  # pragma: no cover
        raise UpstreamProviderError("unused", status_code=429, type="rate_limit_error")
        yield  # makes this an async generator (never reached)


def test_returns_200_and_openai_shape(client, chat_payload):
    resp = client.post("/v1/chat/completions", json=chat_payload())
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body["id"], str) and body["id"].startswith("chatcmpl-")
    assert body["object"] == "chat.completion"
    assert isinstance(body["created"], int) and body["created"] > 0
    assert body["model"] == "mock/echo-1"

    choice = body["choices"][0]
    assert choice["index"] == 0
    assert choice["message"]["role"] == "assistant"
    assert isinstance(choice["message"]["content"], str) and choice["message"]["content"]
    assert choice["finish_reason"] == "stop"

    usage = body["usage"]
    assert usage["total_tokens"] == usage["prompt_tokens"] + usage["completion_tokens"]


def test_system_fingerprint_omitted_when_absent(client, chat_payload):
    body = client.post("/v1/chat/completions", json=chat_payload()).json()
    assert "system_fingerprint" not in body  # exclude_none drops unset optionals


def test_model_string_passthrough_echoed(client, chat_payload):
    body = client.post("/v1/chat/completions", json=chat_payload(model="foo/bar-9")).json()
    assert body["model"] == "foo/bar-9"


def test_multi_message_conversation(client, chat_payload):
    payload = chat_payload(
        messages=[
            {"role": "system", "content": "be terse"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
            {"role": "user", "content": "bye"},
        ]
    )
    body = client.post("/v1/chat/completions", json=payload).json()
    assert len(body["choices"]) == 1
    assert body["choices"][0]["finish_reason"] == "stop"


def test_deterministic_across_identical_requests(client, chat_payload):
    payload = chat_payload()
    a = client.post("/v1/chat/completions", json=payload).json()
    b = client.post("/v1/chat/completions", json=payload).json()
    assert a["id"] == b["id"]
    assert a["created"] == b["created"]
    assert a["choices"][0]["message"]["content"] == b["choices"][0]["message"]["content"]


def test_n_greater_than_one_still_returns_one_choice(client, chat_payload):
    # Documented F1 behavior: the mock ignores n and always returns one choice.
    body = client.post("/v1/chat/completions", json=chat_payload(n=2)).json()
    assert len(body["choices"]) == 1


def test_nonstream_upstream_error_renders_mapped_envelope(client, chat_payload):
    # an UpstreamProviderError from complete() renders over HTTP with its mapped
    # status + OpenAI envelope (type/code), generic message, no key/internal leak
    app.dependency_overrides[get_provider] = lambda: _UpstreamFailingProvider()
    resp = client.post("/v1/chat/completions", json=chat_payload())
    assert resp.status_code == 429
    err = resp.json()["error"]
    assert err["type"] == "rate_limit_error"
    assert err["code"] == "rate_limit_exceeded"
    assert "30" in err["message"]  # retry-after surfaced
    assert set(err) == {"message", "type", "param", "code"}
