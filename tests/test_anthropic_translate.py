"""Unit tests for the pure OpenAI<->Anthropic translators (no SDK, no key)."""

from __future__ import annotations

import pytest

from aegis.gateway.errors import UnsupportedFeatureError
from aegis.gateway.providers.anthropic_translate import (
    clamp_temperature,
    from_anthropic_message,
    hoist_system,
    map_finish_reason,
    strip_model_prefix,
    to_anthropic_params,
    translate_stream_events,
)
from aegis.gateway.schemas import ChatCompletionRequest


def _req(**overrides) -> ChatCompletionRequest:
    body = {"model": "anthropic/claude-opus-4-8", "messages": [{"role": "user", "content": "hi"}]}
    body.update(overrides)
    return ChatCompletionRequest(**body)


# --- small pure helpers ----------------------------------------------------- #
def test_strip_model_prefix():
    assert strip_model_prefix("anthropic/claude-opus-4-8") == "claude-opus-4-8"
    assert strip_model_prefix("claude-haiku-4-5") == "claude-haiku-4-5"
    assert strip_model_prefix("openai/anthropic/x") == "openai/anthropic/x"  # only leading


@pytest.mark.parametrize(
    "value,expected", [(1.5, 1.0), (2.0, 1.0), (0.5, 0.5), (0.0, 0.0), (-0.3, 0.0), (1.0, 1.0)]
)
def test_clamp_temperature(value, expected):
    assert clamp_temperature(value) == expected


@pytest.mark.parametrize(
    "stop_reason,finish",
    [
        ("end_turn", "stop"),
        ("stop_sequence", "stop"),
        ("max_tokens", "length"),
        ("tool_use", "tool_calls"),
        ("refusal", "content_filter"),
        ("pause_turn", "stop"),
        (None, "stop"),  # never null
        ("something_new", "stop"),  # catch-all, never KeyError
    ],
)
def test_map_finish_reason(stop_reason, finish):
    assert map_finish_reason(stop_reason) == finish


# --- system hoisting -------------------------------------------------------- #
def test_hoist_system_concatenates_and_keeps_conversation():
    req = _req(
        messages=[
            {"role": "system", "content": "be terse"},
            {"role": "developer", "content": "use markdown"},
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ]
    )
    system, convo = hoist_system(req.messages)
    assert system == "be terse\n\nuse markdown"
    assert convo == [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]


def test_hoist_system_none_when_absent():
    system, convo = hoist_system(_req().messages)
    assert system is None
    assert convo == [{"role": "user", "content": "hi"}]


# --- request translation ---------------------------------------------------- #
def test_to_anthropic_params_basics_and_prefix_strip():
    params = to_anthropic_params(_req(), default_max_tokens=4096)
    assert params["model"] == "claude-opus-4-8"
    assert params["messages"] == [{"role": "user", "content": "hi"}]
    assert params["max_tokens"] == 4096
    assert "system" not in params


def test_max_tokens_precedence():
    assert (
        to_anthropic_params(_req(max_completion_tokens=10, max_tokens=20), 4096)["max_tokens"] == 10
    )
    assert to_anthropic_params(_req(max_tokens=20), 4096)["max_tokens"] == 20
    assert to_anthropic_params(_req(), 4096)["max_tokens"] == 4096


def test_temperature_clamped_and_top_p_passed_and_stop_mapped():
    params = to_anthropic_params(_req(temperature=1.7, top_p=0.9, stop="END"), 4096)
    assert params["temperature"] == 1.0  # clamped from 1.7
    assert params["top_p"] == 0.9
    assert params["stop_sequences"] == ["END"]  # schema normalized str -> list


def test_to_anthropic_params_rejects_tools():
    with pytest.raises(UnsupportedFeatureError):
        to_anthropic_params(_req(tools=[{"type": "function"}]), 4096)


def test_to_anthropic_params_rejects_tool_choice():
    with pytest.raises(UnsupportedFeatureError):
        to_anthropic_params(_req(tool_choice="auto"), 4096)


def test_to_anthropic_params_rejects_tool_role_message():
    req = _req(messages=[{"role": "user", "content": "x"}, {"role": "tool", "content": "r"}])
    with pytest.raises(UnsupportedFeatureError):
        to_anthropic_params(req, 4096)


def test_to_anthropic_params_rejects_non_text_content():
    req = _req(
        messages=[{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x"}}]}]
    )
    with pytest.raises(UnsupportedFeatureError):
        to_anthropic_params(req, 4096)


def test_text_only_multimodal_parts_are_allowed():
    req = _req(messages=[{"role": "user", "content": [{"type": "text", "text": "hi there"}]}])
    params = to_anthropic_params(req, 4096)
    assert params["messages"] == [{"role": "user", "content": "hi there"}]


# --- response translation --------------------------------------------------- #
def test_from_anthropic_message_maps_everything():
    msg = {
        "id": "msg_123",
        "content": [{"type": "text", "text": "Hello"}, {"type": "text", "text": " world"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 3, "output_tokens": 2},
    }
    resp = from_anthropic_message(msg, "anthropic/claude-opus-4-8", created=123)
    assert resp.id == "msg_123"
    assert resp.created == 123
    assert resp.model == "anthropic/claude-opus-4-8"  # original request model echoed
    assert resp.choices[0].message.content == "Hello world"
    assert resp.choices[0].finish_reason == "stop"
    assert (resp.usage.prompt_tokens, resp.usage.completion_tokens, resp.usage.total_tokens) == (
        3,
        2,
        5,
    )


def test_from_anthropic_message_handles_missing_usage_and_id():
    resp = from_anthropic_message({"content": [], "stop_reason": "max_tokens"}, "m", created=1)
    assert resp.id == "chatcmpl-anthropic"
    assert resp.choices[0].finish_reason == "length"
    assert resp.usage.total_tokens == 0


# --- streaming -------------------------------------------------------------- #
def _events(stop_reason="end_turn"):
    return [
        {"type": "message_start", "message": {"usage": {"input_tokens": 5}}},
        {"type": "content_block_start", "index": 0},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hel"}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "lo"}},
        {"type": "content_block_stop"},
        {
            "type": "message_delta",
            "delta": {"stop_reason": stop_reason},
            "usage": {"output_tokens": 2},
        },
        {"type": "message_stop"},
    ]


def test_stream_sequence_role_content_and_terminal_finish_reason():
    chunks = translate_stream_events(_events(), chunk_id="c1", created=7, model="m")
    # role chunk, two content chunks, terminal chunk
    assert chunks[0].choices[0].delta.role == "assistant"
    assert [c.choices[0].delta.content for c in chunks[1:3]] == ["Hel", "lo"]
    terminal = chunks[-1]
    # THE BUG GUARD: finish_reason comes from message_delta, is "stop" not null
    assert terminal.choices[0].finish_reason == "stop"
    assert terminal.choices[0].delta.content is None
    # stable id/created/model across all chunks
    assert {c.id for c in chunks} == {"c1"}
    assert {c.created for c in chunks} == {7}


def test_stream_adopts_real_message_id():
    events = [
        {"type": "message_start", "message": {"id": "msg_real", "usage": {"input_tokens": 1}}},
        {"type": "message_stop"},
    ]
    chunks = translate_stream_events(events, chunk_id="placeholder", created=1, model="m")
    assert {c.id for c in chunks} == {"msg_real"}


def test_stream_finish_reason_length_from_message_delta():
    chunks = translate_stream_events(_events("max_tokens"), chunk_id="c", created=1, model="m")
    assert chunks[-1].choices[0].finish_reason == "length"


def test_stream_no_usage_chunk_by_default():
    chunks = translate_stream_events(_events(), chunk_id="c", created=1, model="m")
    assert all(c.usage is None for c in chunks)
    assert chunks[-1].choices  # terminal chunk has a choice, not a usage-only chunk


def test_stream_usage_chunk_when_requested():
    chunks = translate_stream_events(
        _events(), chunk_id="c", created=1, model="m", include_usage=True
    )
    usage_chunk = chunks[-1]
    assert usage_chunk.choices == []
    assert usage_chunk.usage.prompt_tokens == 5
    assert usage_chunk.usage.completion_tokens == 2
    assert usage_chunk.usage.total_tokens == 7


def test_stream_skips_empty_text_and_unknown_events():
    events = [
        {"type": "message_start", "message": {"usage": {}}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": ""}},
        {"type": "ping"},
        {"type": "message_stop"},
    ]
    chunks = translate_stream_events(events, chunk_id="c", created=1, model="m")
    # role chunk + terminal only (empty text and ping produce nothing)
    assert len(chunks) == 2
    assert chunks[0].choices[0].delta.role == "assistant"
    assert chunks[-1].choices[0].finish_reason == "stop"
