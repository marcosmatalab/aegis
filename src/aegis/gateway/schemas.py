"""OpenAI-compatible wire models for ``/v1/chat/completions`` (pydantic v2).

This module is PURE: it imports nothing from FastAPI or the rest of the
gateway, so every model is unit-testable in isolation. The error envelope lives
in :mod:`aegis.gateway.errors` (single source of truth) — not here.

Design intent (drop-in compatibility):
  * Inbound request/message models use ``extra="allow"`` so newer OpenAI params
    (e.g. ``stream_options``, ``parallel_tool_calls``, ``reasoning_effort``)
    are preserved and can be forwarded verbatim — they are never rejected.
  * Only the essentials are validated hard: ``messages`` non-empty, ``role`` in
    a closed set, and numeric bounds on the well-known sampling knobs.
  * ``object`` and ``finish_reason`` are ``Literal`` so they can never serialize
    to a value an OpenAI SDK would not recognise.

Serialization contract (used by the proxy):
  * Non-streaming responses: ``model_dump(exclude_none=True)`` — omit unset
    optionals (e.g. ``system_fingerprint``), matching OpenAI.
  * Streaming chunks are serialized by the proxy with a custom helper that keeps
    ``finish_reason`` present (even ``null``) while emitting an empty terminal
    ``delta`` as ``{}``. (Do NOT blanket-apply ``exclude_none`` to chunks.)
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Role = Literal["system", "user", "assistant", "tool", "developer"]
FinishReason = Literal["stop", "length", "tool_calls", "content_filter", "function_call"]


# --------------------------------------------------------------------------- #
# Inbound request
# --------------------------------------------------------------------------- #
class ChatMessage(BaseModel):
    """A single inbound chat message. ``extra="allow"`` keeps fields such as
    ``tool_calls``, ``tool_call_id`` and ``refusal`` for passthrough."""

    model_config = ConfigDict(extra="allow")

    role: Role
    content: str | list[dict[str, Any]] | None = None
    name: str | None = None

    @model_validator(mode="after")
    def _require_content_for_user(self):
        # Minimal local strictness: a user turn must carry content (caught even
        # when the field is omitted entirely). Other roles (assistant tool-calls,
        # tool results, system/developer) may legitimately omit it, so we leave
        # those to the provider to avoid rejecting valid traffic.
        if self.role == "user" and self.content is None:
            raise ValueError("content is required for role 'user'")
        return self


class ChatCompletionRequest(BaseModel):
    """OpenAI ``/v1/chat/completions`` request. ``extra="allow"`` forwards
    unknown/newer params untouched."""

    model_config = ConfigDict(extra="allow")

    model: str = Field(min_length=1)
    messages: list[ChatMessage] = Field(min_length=1)
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    top_p: float | None = Field(default=None, ge=0.0, le=1.0)
    n: int | None = Field(default=1, ge=1)
    stream: bool = False
    stop: str | list[str] | None = None
    max_tokens: int | None = Field(default=None, ge=0)
    max_completion_tokens: int | None = Field(default=None, ge=0)
    presence_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    frequency_penalty: float | None = Field(default=None, ge=-2.0, le=2.0)
    logit_bias: dict[str, int] | None = None
    user: str | None = None
    seed: int | None = Field(default=None, ge=0)
    response_format: dict[str, Any] | None = None
    tools: list[dict[str, Any]] | None = None
    tool_choice: str | dict[str, Any] | None = None

    @field_validator("stop")
    @classmethod
    def _normalize_stop(cls, v):
        return [v] if isinstance(v, str) else v


# --------------------------------------------------------------------------- #
# Outbound: non-streaming response
# --------------------------------------------------------------------------- #
class ResponseMessage(BaseModel):
    """Assistant message in a completion. ``content`` mirrors the request union
    so structured/multimodal assistant content from a real provider round-trips."""

    model_config = ConfigDict(extra="allow")

    role: Literal["assistant"] = "assistant"
    content: str | list[dict[str, Any]] | None = None


class Choice(BaseModel):
    index: int
    message: ResponseMessage
    finish_reason: FinishReason | None = None


class Usage(BaseModel):
    model_config = ConfigDict(extra="allow")  # allow *_tokens_details passthrough

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: Literal["chat.completion"] = "chat.completion"
    created: int
    model: str
    choices: list[Choice]
    usage: Usage
    system_fingerprint: str | None = None


# --------------------------------------------------------------------------- #
# Outbound: streaming chunks
# --------------------------------------------------------------------------- #
class Delta(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: Literal["assistant"] | None = None
    content: str | None = None


class ChunkChoice(BaseModel):
    index: int
    delta: Delta
    finish_reason: FinishReason | None = None


class ChatCompletionChunk(BaseModel):
    id: str
    object: Literal["chat.completion.chunk"] = "chat.completion.chunk"
    created: int
    model: str
    choices: list[ChunkChoice]
    system_fingerprint: str | None = None
    usage: Usage | None = None
