"""Streaming (SSE) POST /v1/chat/completions contract."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from aegis.gateway.errors import UpstreamProviderError
from aegis.gateway.main import app
from aegis.gateway.proxy import get_provider
from aegis.gateway.schemas import ChatCompletionChunk, ChunkChoice, Delta
from aegis.gateway.upstream import Provider


class _BoomProvider(Provider):
    """Streams one valid chunk, then raises mid-stream (after headers are sent)."""

    name = "boom"

    async def complete(self, request):  # pragma: no cover - not used by these tests
        raise RuntimeError("boom")

    async def stream(self, request) -> AsyncIterator[ChatCompletionChunk]:
        yield ChatCompletionChunk(
            id="chatcmpl-boom",
            created=1,
            model=request.model,
            choices=[ChunkChoice(index=0, delta=Delta(role="assistant"), finish_reason=None)],
        )
        raise RuntimeError("boom mid-stream")


class _MappedErrorProvider(Provider):
    """Raises a mapped AegisError mid-stream (e.g. an upstream rate limit)."""

    name = "mapped"

    async def complete(self, request):  # pragma: no cover - not used by these tests
        raise RuntimeError("unused")

    async def stream(self, request) -> AsyncIterator[ChatCompletionChunk]:
        yield ChatCompletionChunk(
            id="chatcmpl-x",
            created=1,
            model=request.model,
            choices=[ChunkChoice(index=0, delta=Delta(role="assistant"), finish_reason=None)],
        )
        raise UpstreamProviderError(
            "upstream rate limit exceeded",
            status_code=429,
            type="rate_limit_error",
            code="rate_limit_exceeded",
        )


def test_content_type_is_event_stream(client, chat_payload):
    resp = client.post("/v1/chat/completions", json=chat_payload(stream=True))
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")


def test_framing_and_chunk_sequence(client, chat_payload, parse_sse):
    resp = client.post("/v1/chat/completions", json=chat_payload(stream=True))
    events = parse_sse(resp)
    assert events[-1] == "[DONE]"

    chunks = [e for e in events if e != "[DONE]"]
    assert all(c["object"] == "chat.completion.chunk" for c in chunks)
    # first chunk announces the role only
    assert chunks[0]["choices"][0]["delta"] == {"role": "assistant"}
    # at least one content delta
    assert any(c["choices"][0]["delta"].get("content") for c in chunks)
    # terminal chunk: empty delta + finish_reason 'stop'
    assert chunks[-1]["choices"][0]["delta"] == {}
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


def test_finish_reason_null_present_midstream(client, chat_payload):
    # Raw assertion: non-terminal chunks carry the key as JSON null (compact form).
    resp = client.post("/v1/chat/completions", json=chat_payload(stream=True))
    assert '"finish_reason":null' in resp.text


def test_stream_ends_with_done_sentinel(client, chat_payload):
    resp = client.post("/v1/chat/completions", json=chat_payload(stream=True))
    assert resp.text.endswith("data: [DONE]\n\n")


def test_chunk_ids_and_created_consistent(client, chat_payload, parse_sse):
    resp = client.post("/v1/chat/completions", json=chat_payload(stream=True))
    chunks = [e for e in parse_sse(resp) if e != "[DONE]"]
    assert len({c["id"] for c in chunks}) == 1
    assert len({c["created"] for c in chunks}) == 1
    assert chunks[0]["id"].startswith("chatcmpl-")


@pytest.mark.parametrize("prompt", ["x", "many words make several content chunks here"])
def test_chunking_scales_but_terminates(client, chat_payload, parse_sse, prompt):
    resp = client.post(
        "/v1/chat/completions",
        json=chat_payload(stream=True, messages=[{"role": "user", "content": prompt}]),
    )
    chunks = [e for e in parse_sse(resp) if e != "[DONE]"]
    content_chunks = [c for c in chunks if c["choices"][0]["delta"].get("content")]
    assert len(content_chunks) >= 1
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"


def test_streamed_content_matches_nonstreamed(client, chat_payload, parse_sse):
    payload = chat_payload()
    full = client.post("/v1/chat/completions", json=payload).json()
    resp = client.post("/v1/chat/completions", json={**payload, "stream": True})
    chunks = [e for e in parse_sse(resp) if e != "[DONE]"]
    streamed = "".join(c["choices"][0]["delta"].get("content", "") for c in chunks)
    assert streamed == full["choices"][0]["message"]["content"]


def test_chunks_omit_null_usage_and_fingerprint(client, chat_payload, parse_sse):
    # OpenAI omits these on default streams; we must not emit them as null.
    resp = client.post("/v1/chat/completions", json=chat_payload(stream=True))
    chunks = [e for e in parse_sse(resp) if e != "[DONE]"]
    for chunk in chunks:
        assert "usage" not in chunk
        assert "system_fingerprint" not in chunk


def test_midstream_error_emits_error_frame_without_done(client, parse_sse):
    app.dependency_overrides[get_provider] = lambda: _BoomProvider()
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "m", "messages": [{"role": "user", "content": "hi"}], "stream": True},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")

    frames = parse_sse(resp)
    error_frames = [f for f in frames if isinstance(f, dict) and "error" in f]
    assert len(error_frames) == 1
    assert error_frames[0]["error"]["type"] == "api_error"
    # OpenAI sends no [DONE] after an error frame.
    assert "[DONE]" not in resp.text


def test_midstream_mapped_error_frame_carries_type_and_code(client, parse_sse):
    # a mapped AegisError surfaces its real type/code in the SSE error frame
    # (richer than the generic api_error), still with no [DONE].
    app.dependency_overrides[get_provider] = lambda: _MappedErrorProvider()
    resp = client.post(
        "/v1/chat/completions",
        json={"model": "m", "messages": [{"role": "user", "content": "hi"}], "stream": True},
    )
    assert resp.status_code == 200
    error_frames = [f for f in parse_sse(resp) if isinstance(f, dict) and "error" in f]
    assert len(error_frames) == 1
    assert error_frames[0]["error"]["type"] == "rate_limit_error"
    assert error_frames[0]["error"]["code"] == "rate_limit_exceeded"
    assert "[DONE]" not in resp.text
