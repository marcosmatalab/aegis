"""Streaming (SSE) POST /v1/chat/completions contract."""

from __future__ import annotations

import pytest


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
