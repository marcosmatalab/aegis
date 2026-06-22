"""Unit tests for the provider factory, MockProvider, and the pure helpers."""

from __future__ import annotations

import asyncio

import pytest

from aegis.gateway.errors import ProviderNotConfiguredError
from aegis.gateway.schemas import ChatCompletionRequest
from aegis.gateway.upstream import (
    MockProvider,
    Provider,
    _canned_answer,
    _content_to_text,
    _count_tokens,
    _derive_created,
    _split_into_deltas,
    build_provider,
)


def _req(**overrides) -> ChatCompletionRequest:
    body = {"model": "mock/echo-1", "messages": [{"role": "user", "content": "ping"}]}
    body.update(overrides)
    return ChatCompletionRequest(**body)


def _collect(agen):
    async def _run():
        return [item async for item in agen]

    return asyncio.run(_run())


# --- pure helpers ----------------------------------------------------------- #
def test_content_to_text_variants():
    assert _content_to_text("hello") == "hello"
    assert _content_to_text(None) == ""
    assert _content_to_text([{"type": "text", "text": "a"}, {"type": "text", "text": "b"}]) == "a b"


def test_count_tokens_empty_is_zero():
    assert _count_tokens("") == 0
    assert _count_tokens("one two three") == 3


@pytest.mark.parametrize("text", ["", "x", "ab", "Echo: ping", "héllo 🌍 wörld", "a  b   c"])
def test_split_into_deltas_is_lossless(text):
    slices = _split_into_deltas(text)
    assert "".join(slices) == text
    assert all(s != "" for s in slices)  # never emit an empty content delta
    if text == "":
        assert slices == []


def test_canned_answer_echoes_last_user_message():
    assert _canned_answer(_req(messages=[{"role": "user", "content": "hola"}])) == "Echo: hola"


def test_canned_answer_fallback_without_user_text():
    req = _req(messages=[{"role": "system", "content": "be nice"}])
    assert _canned_answer(req).startswith("Hello!")


def test_canned_answer_empty_user_content_falls_back():
    # content="" is accepted (only None is rejected for a user turn) but the
    # empty string is falsy, so the generic fallback answer is used.
    req = _req(messages=[{"role": "user", "content": ""}])
    assert _canned_answer(req).startswith("Hello!")


def test_derive_created_is_positive():
    # All-zero hex prefix would give 0; the "or 1" guard prevents created == 0.
    assert _derive_created("00000000ffff") == 1
    assert _derive_created("0000000a") == 10


# --- factory ---------------------------------------------------------------- #
def test_build_provider_returns_mock():
    provider = build_provider("mock")
    assert isinstance(provider, MockProvider)
    assert isinstance(provider, Provider)
    assert provider.name == "mock"


@pytest.mark.parametrize("name", ["anthropic", "openai", "google", "ghost"])
def test_build_provider_unconfigured_raises(name):
    with pytest.raises(ProviderNotConfiguredError) as exc:
        build_provider(name)
    assert name in str(exc.value)


# --- MockProvider.complete -------------------------------------------------- #
def test_complete_returns_openai_shape():
    resp = asyncio.run(MockProvider().complete(_req()))
    assert resp.object == "chat.completion"
    assert resp.id.startswith("chatcmpl-")
    assert resp.created > 0
    assert resp.model == "mock/echo-1"
    assert len(resp.choices) == 1
    choice = resp.choices[0]
    assert choice.index == 0
    assert choice.message.role == "assistant"
    assert choice.finish_reason == "stop"
    assert resp.usage.total_tokens == resp.usage.prompt_tokens + resp.usage.completion_tokens


def test_complete_is_deterministic():
    a = asyncio.run(MockProvider().complete(_req()))
    b = asyncio.run(MockProvider().complete(_req()))
    assert a.id == b.id
    assert a.created == b.created
    assert a.choices[0].message.content == b.choices[0].message.content


def test_complete_handles_multimodal_and_none_content():
    req = _req(
        messages=[
            {"role": "system", "content": None},
            {"role": "user", "content": [{"type": "text", "text": "describe"}]},
        ]
    )
    resp = asyncio.run(MockProvider().complete(req))
    # multimodal text part is flattened and echoed; None content contributes 0 tokens
    assert resp.choices[0].message.content == "Echo: describe"
    assert resp.usage.prompt_tokens == 1
    assert resp.choices[0].finish_reason == "stop"


# --- MockProvider.stream ---------------------------------------------------- #
def test_stream_chunk_sequence_and_reassembly():
    req = _req()
    chunks = _collect(MockProvider().stream(req))
    assert all(c.object == "chat.completion.chunk" for c in chunks)

    # first chunk announces the role only
    assert chunks[0].choices[0].delta.role == "assistant"
    assert chunks[0].choices[0].delta.content is None
    assert chunks[0].choices[0].finish_reason is None

    # terminal chunk carries finish_reason='stop' with an empty delta
    last = chunks[-1]
    assert last.choices[0].finish_reason == "stop"
    assert last.choices[0].delta.role is None
    assert last.choices[0].delta.content is None

    # mid chunks reassemble to the non-streamed answer
    streamed = "".join(c.choices[0].delta.content or "" for c in chunks)
    full = asyncio.run(MockProvider().complete(req))
    assert streamed == full.choices[0].message.content

    # ids/created stable across all chunks and equal to the non-streamed id
    assert {c.id for c in chunks} == {full.id}
    assert {c.created for c in chunks} == {full.created}


def test_stream_is_deterministic():
    a = _collect(MockProvider().stream(_req()))
    b = _collect(MockProvider().stream(_req()))
    assert [c.model_dump() for c in a] == [c.model_dump() for c in b]
