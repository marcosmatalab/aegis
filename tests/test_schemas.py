"""Unit tests for the pure OpenAI-compatible Pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aegis.gateway.schemas import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    Choice,
    ChunkChoice,
    Delta,
    ResponseMessage,
    Usage,
)


def _req(**overrides):
    body = {"model": "mock/echo-1", "messages": [{"role": "user", "content": "hi"}]}
    body.update(overrides)
    return body


# --- request / message validation ------------------------------------------ #
def test_minimal_request_ok():
    r = ChatCompletionRequest(**_req())
    assert r.model == "mock/echo-1"
    assert r.stream is False
    assert r.n == 1


def test_empty_messages_rejected():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(**_req(messages=[]))


def test_missing_model_rejected():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(messages=[{"role": "user", "content": "hi"}])


def test_blank_model_rejected():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(**_req(model=""))


def test_invalid_role_rejected():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(**_req(messages=[{"role": "wizard", "content": "x"}]))


def test_user_message_requires_content():
    with pytest.raises(ValidationError):
        ChatMessage(role="user")
    with pytest.raises(ValidationError):
        ChatMessage(role="user", content=None)


def test_non_user_roles_may_omit_content():
    # assistant tool-call / tool result / system may legitimately omit content
    assert ChatMessage(role="assistant", content=None).content is None
    assert ChatMessage(role="tool", content=None).content is None
    assert ChatMessage(role="system", content=None).content is None


def test_multimodal_list_content_accepted():
    msg = ChatMessage(
        role="user",
        content=[{"type": "text", "text": "hi"}, {"type": "image_url", "image_url": {}}],
    )
    assert isinstance(msg.content, list)


def test_n_zero_rejected():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(**_req(n=0))


def test_seed_negative_rejected():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(**_req(seed=-1))


@pytest.mark.parametrize("temperature", [-0.1, 2.1])
def test_temperature_out_of_bounds_rejected(temperature):
    with pytest.raises(ValidationError):
        ChatCompletionRequest(**_req(temperature=temperature))


def test_stop_string_normalized_to_list():
    r = ChatCompletionRequest(**_req(stop="END"))
    assert r.stop == ["END"]


def test_stop_list_preserved():
    r = ChatCompletionRequest(**_req(stop=["a", "b"]))
    assert r.stop == ["a", "b"]


def test_unknown_params_preserved_in_model_extra():
    r = ChatCompletionRequest(**_req(parallel_tool_calls=True, reasoning_effort="high"))
    assert r.model_extra["parallel_tool_calls"] is True
    assert r.model_extra["reasoning_effort"] == "high"


def test_tool_choice_accepts_str_and_dict():
    assert ChatCompletionRequest(**_req(tool_choice="auto")).tool_choice == "auto"
    choice = {"type": "function", "function": {"name": "f"}}
    assert ChatCompletionRequest(**_req(tool_choice=choice)).tool_choice == choice


# --- response / chunk shape -------------------------------------------------- #
def test_response_object_discriminator_is_pinned():
    resp = ChatCompletionResponse(
        id="chatcmpl-x",
        created=1,
        model="m",
        choices=[Choice(index=0, message=ResponseMessage(content="hi"), finish_reason="stop")],
        usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
    )
    assert resp.object == "chat.completion"
    # exclude_none drops absent optionals (matches OpenAI's omission of them)
    dumped = resp.model_dump(exclude_none=True)
    assert "system_fingerprint" not in dumped


def test_chunk_object_discriminator_is_pinned():
    chunk = ChatCompletionChunk(
        id="chatcmpl-x",
        created=1,
        model="m",
        choices=[ChunkChoice(index=0, delta=Delta(role="assistant"), finish_reason=None)],
    )
    assert chunk.object == "chat.completion.chunk"
    assert chunk.choices[0].finish_reason is None


def test_invalid_finish_reason_rejected():
    with pytest.raises(ValidationError):
        Choice(index=0, message=ResponseMessage(content="x"), finish_reason="explode")
