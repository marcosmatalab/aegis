"""Unit tests for the pure OpenAI<->Anthropic translators (no SDK, no key)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from aegis.gateway.errors import UnsupportedFeatureError
from aegis.gateway.providers.anthropic_translate import (
    _forbids_sampling_params,
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
    # claude-opus-4-6 ACCEPTS sampling params (the _req() default 4-8 now omits them)
    params = to_anthropic_params(
        _req(model="claude-opus-4-6", temperature=1.7, top_p=0.9, stop="END"), 4096
    )
    assert params["temperature"] == 1.0  # clamped from 1.7
    assert params["top_p"] == 0.9
    assert params["stop_sequences"] == ["END"]  # schema normalized str -> list


# --- sampling-param omission for models that reject them (Opus 4.7+) --------- #
@pytest.mark.parametrize(
    "model",
    [
        "claude-opus-4-7",
        "claude-opus-4-8",
        "anthropic/claude-opus-4-8",
        "claude-opus-4-10",  # numeric minor compare: 10 >= 7 (not lexical '10' < '7')
        "claude-opus-4-7-20991231",  # dated suffix on a forbidding id
        "claude-opus-4-8-preview",  # non-date alias suffix still forbids
        "claude-opus-5",  # bare major 5, no minor -> forbid
        "claude-opus-5-0",
        "CLAUDE-OPUS-4-8",  # case-insensitive
        "  claude-opus-4-8  ",  # whitespace-padded
        " anthropic/claude-opus-4-8",  # leading space before the prefix
        "ANTHROPIC/claude-opus-4-8",  # uppercase provider prefix (must still strip)
        "Anthropic/claude-opus-4-8",  # mixed-case provider prefix
    ],
)
def test_forbids_sampling_params_true(model):
    assert _forbids_sampling_params(model) is True


@pytest.mark.parametrize(
    "model",
    [
        "claude-opus-4-6",  # boundary just below 4.7
        "claude-opus-4-1-20250805",  # dated suffix not read as the minor
        "claude-opus-4-0",
        "claude-opus-4",  # missing minor -> 0 -> allow
        "claude-3-opus-20240229",  # legacy scheme: family after the number
        "anthropic/claude-3-opus-20240229",
        "claude-sonnet-4-6",
        "claude-sonnet-4-8",  # only Opus forbids, not version alone
        "claude-haiku-4-5",
        "gpt-4o",  # non-Anthropic
        "",
    ],
)
def test_forbids_sampling_params_false(model):
    assert _forbids_sampling_params(model) is False


def test_forbidding_model_omits_sampling_params():
    # temperature=0.0 specifically: proves the FORBID gate drops it, not the None-skip
    params = to_anthropic_params(
        _req(model="anthropic/claude-opus-4-8", temperature=0.0, top_p=0.9, stop="END"), 4096
    )
    assert "temperature" not in params
    assert "top_p" not in params
    assert "top_k" not in params
    # non-sampling fields survive: only the sampling knobs are dropped
    assert params["model"] == "claude-opus-4-8"
    assert params["max_tokens"] == 4096
    assert params["stop_sequences"] == ["END"]


def test_accepting_model_keeps_clamped_sampling_params():
    params = to_anthropic_params(_req(model="claude-sonnet-4-6", temperature=1.7, top_p=0.9), 4096)
    assert params["temperature"] == 1.0  # clamped
    assert params["top_p"] == 0.9


def test_boundary_opus_4_6_keeps_vs_4_7_omits_via_full_path():
    keeps = to_anthropic_params(_req(model="claude-opus-4-6", temperature=0.0), 4096)
    omits = to_anthropic_params(_req(model="claude-opus-4-7", temperature=0.0), 4096)
    assert keeps["temperature"] == 0.0
    assert "temperature" not in omits


def test_legacy_claude_3_opus_keeps_temperature():
    # Claude 3 Opus accepts sampling params; must NOT be over-forbidden
    params = to_anthropic_params(_req(model="claude-3-opus-20240229", temperature=0.5), 4096)
    assert params["temperature"] == 0.5


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


def test_multimodal_text_parts_concatenated_verbatim():
    # parts concatenated with NO injected separator and NO strip (mirrors the
    # response-side join); the user's text is never mutated
    req = _req(
        messages=[
            {
                "role": "user",
                "content": [{"type": "text", "text": "line1\n"}, {"type": "text", "text": "line2"}],
            }
        ]
    )
    params = to_anthropic_params(req, 4096)
    assert params["messages"] == [{"role": "user", "content": "line1\nline2"}]


def test_string_content_is_not_trimmed():
    req = _req(messages=[{"role": "user", "content": "  hello  "}])
    assert to_anthropic_params(req, 4096)["messages"][0]["content"] == "  hello  "


def test_max_tokens_zero_is_honored_not_replaced_by_default():
    # explicit 0 must not be silently swallowed by the `or default` falsy trap
    assert to_anthropic_params(_req(max_completion_tokens=0), 4096)["max_tokens"] == 0
    assert to_anthropic_params(_req(max_tokens=0), 4096)["max_tokens"] == 0


def test_rejects_assistant_tool_calls_in_history():
    req = _req(
        messages=[
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "t1", "type": "function", "function": {"name": "f"}}],
            },
        ]
    )
    with pytest.raises(UnsupportedFeatureError):
        to_anthropic_params(req, 4096)


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


def test_from_anthropic_message_accepts_attribute_objects():
    # the REAL SDK returns pydantic objects (attribute access), not dicts — this
    # exercises the getattr branch of _get that the live path actually hits
    msg = SimpleNamespace(
        id="msg_attr",
        content=[SimpleNamespace(type="text", text="Hi")],
        stop_reason="end_turn",
        usage=SimpleNamespace(input_tokens=2, output_tokens=1),
    )
    resp = from_anthropic_message(msg, "m", created=1)
    assert resp.id == "msg_attr"
    assert resp.choices[0].message.content == "Hi"
    assert resp.choices[0].finish_reason == "stop"
    assert resp.usage.total_tokens == 3


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


def test_stream_accepts_attribute_event_objects():
    # real SDK stream events are attribute objects, not dicts — exercise getattr
    events = [
        SimpleNamespace(
            type="message_start",
            message=SimpleNamespace(id="msg_a", usage=SimpleNamespace(input_tokens=2)),
        ),
        SimpleNamespace(
            type="content_block_delta", delta=SimpleNamespace(type="text_delta", text="Hi")
        ),
        SimpleNamespace(
            type="message_delta",
            delta=SimpleNamespace(stop_reason="end_turn"),
            usage=SimpleNamespace(output_tokens=1),
        ),
        SimpleNamespace(type="message_stop"),
    ]
    chunks = translate_stream_events(events, chunk_id="x", created=1, model="m")
    assert chunks[0].choices[0].delta.role == "assistant"
    assert chunks[1].choices[0].delta.content == "Hi"
    assert chunks[-1].choices[0].finish_reason == "stop"
    assert {c.id for c in chunks} == {"msg_a"}


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
