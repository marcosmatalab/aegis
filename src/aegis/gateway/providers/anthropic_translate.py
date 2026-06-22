"""Pure OpenAI <-> Anthropic Messages API translation — NO SDK import.

Everything here operates on the OpenAI wire models and plain dict/attr objects,
importing nothing from the ``anthropic`` SDK, so the whole translation layer is
unit-testable offline with fakes. The provider module is the only place the SDK
is (lazily) imported.

SCOPE: TEXT completions only. Tool-calling and non-text multimodal content are
REJECTED with a clear 400 (``UnsupportedFeatureError``) rather than silently
dropped — see ``ensure_text_only``. Documented divergences from OpenAI:
  * ``temperature`` is clamped to [0, 1] (Anthropic's max is 1; OpenAI allows 2);
  * ``created`` is a synthesized wall-clock int (Anthropic returns none);
  * ``finish_reason`` falls back to ``"stop"`` for any unrecognized stop reason.
"""

from __future__ import annotations

import time
from typing import Any

from aegis.gateway.errors import UnsupportedFeatureError, UpstreamProviderError
from aegis.gateway.schemas import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Choice,
    ChunkChoice,
    Delta,
    ResponseMessage,
    Usage,
)

_SYSTEM_ROLES = {"system", "developer"}

# Anthropic stop_reason -> OpenAI finish_reason. ``.get(..., "stop")`` is the
# catch-all so an unknown/None stop reason can never KeyError or serialize null.
_FINISH_REASON = {
    "end_turn": "stop",
    "stop_sequence": "stop",
    "max_tokens": "length",
    "tool_use": "tool_calls",
    "refusal": "content_filter",
    "pause_turn": "stop",
}


def _get(obj: Any, key: str, default: Any = None) -> Any:
    """Attribute-or-key access so real SDK pydantic objects and plain dict fakes
    both work in the translators."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def map_finish_reason(stop_reason: str | None) -> str:
    """Map an Anthropic stop_reason to an OpenAI finish_reason; unknown/None ->
    ``"stop"`` (never KeyError, never null)."""
    return _FINISH_REASON.get(stop_reason or "", "stop")


def strip_model_prefix(model: str) -> str:
    """Drop a leading ``anthropic/`` so the bare model id reaches the SDK."""
    return model[len("anthropic/") :] if model.startswith("anthropic/") else model


def clamp_temperature(temperature: float) -> float:
    """Clamp to Anthropic's [0, 1] range (OpenAI allows up to 2)."""
    return max(0.0, min(1.0, temperature))


def _flatten_text(content: str | list[dict[str, Any]] | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = (p.get("text", "") for p in content if isinstance(p, dict))
    return " ".join(t for t in parts if t).strip()


def ensure_text_only(request: ChatCompletionRequest) -> None:
    """Reject (400) the features the adapter does not translate yet, so a client
    is never silently served a feature-dropped answer."""
    if request.tools or request.tool_choice:
        raise UnsupportedFeatureError("tool calling")
    for message in request.messages:
        if message.role == "tool":
            raise UnsupportedFeatureError("tool-result messages")
        if isinstance(message.content, list):
            for part in message.content:
                if isinstance(part, dict) and part.get("type", "text") != "text":
                    raise UnsupportedFeatureError(f"non-text content ({part.get('type')})")


def hoist_system(messages: list) -> tuple[str | None, list[dict[str, str]]]:
    """Pull system/developer turns into Anthropic's top-level ``system`` string
    (concatenated with blank lines) and return the remaining user/assistant turns."""
    system_parts: list[str] = []
    conversation: list[dict[str, str]] = []
    for message in messages:
        if message.role in _SYSTEM_ROLES:
            text = _flatten_text(message.content)
            if text:
                system_parts.append(text)
        else:
            conversation.append({"role": message.role, "content": _flatten_text(message.content)})
    system = "\n\n".join(system_parts) if system_parts else None
    return system, conversation


def to_anthropic_params(request: ChatCompletionRequest, default_max_tokens: int) -> dict[str, Any]:
    """Translate an OpenAI request into Anthropic ``messages.create`` kwargs."""
    ensure_text_only(request)
    system, messages = hoist_system(request.messages)
    params: dict[str, Any] = {
        "model": strip_model_prefix(request.model),
        "messages": messages,
        # Anthropic REQUIRES max_tokens; OpenAI makes it optional.
        "max_tokens": request.max_completion_tokens or request.max_tokens or default_max_tokens,
    }
    if system:
        params["system"] = system
    if request.temperature is not None:
        params["temperature"] = clamp_temperature(request.temperature)
    if request.top_p is not None:
        params["top_p"] = request.top_p
    if request.stop:  # schema already normalized str -> [str]
        params["stop_sequences"] = request.stop
    return params


def _text_from_blocks(content: Any) -> str:
    return "".join(
        _get(block, "text", "") or "" for block in (content or []) if _get(block, "type") == "text"
    )


def from_anthropic_message(
    message: Any, request_model: str, *, created: int | None = None
) -> ChatCompletionResponse:
    """Translate an Anthropic Message into an OpenAI ChatCompletionResponse.

    ``request_model`` (not the bare upstream id) is echoed back so OpenAI clients
    see the model they asked for. ``created`` is injectable for deterministic
    tests; in production it is a wall-clock int."""
    usage = _get(message, "usage")
    prompt_tokens = _get(usage, "input_tokens", 0) or 0
    completion_tokens = _get(usage, "output_tokens", 0) or 0
    return ChatCompletionResponse(
        id=_get(message, "id") or "chatcmpl-anthropic",
        created=created if created is not None else int(time.time()),
        model=request_model,
        choices=[
            Choice(
                index=0,
                message=ResponseMessage(
                    role="assistant", content=_text_from_blocks(_get(message, "content", []))
                ),
                finish_reason=map_finish_reason(_get(message, "stop_reason")),
            )
        ],
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        ),
    )


# --------------------------------------------------------------------------- #
# Streaming: a small stateful translator so the same per-event logic is driven
# by the provider's async loop AND by sync tests (translate_stream_events).
# --------------------------------------------------------------------------- #
class StreamTranslator:
    """Maps Anthropic stream events onto OpenAI chunks.

    Event order: message_start -> content_block_delta(text_delta)* ->
    message_delta(stop_reason + output_tokens) -> message_stop. The terminal
    finish_reason is taken from message_delta (NOT message_stop, which has no
    payload). A usage chunk is emitted on message_stop only when ``include_usage``
    is set (OpenAI's ``stream_options.include_usage`` contract)."""

    def __init__(self, chunk_id: str, created: int, model: str, *, include_usage: bool = False):
        self.id = chunk_id
        self.created = created
        self.model = model
        self.include_usage = include_usage
        self.stop_reason: str | None = None
        self.input_tokens = 0
        self.output_tokens = 0

    def _chunk(self, *, delta: Delta | None, finish_reason, choices=None, usage=None):
        if choices is None:
            choices = [ChunkChoice(index=0, delta=delta or Delta(), finish_reason=finish_reason)]
        return ChatCompletionChunk(
            id=self.id, created=self.created, model=self.model, choices=choices, usage=usage
        )

    def handle(self, event: Any) -> list[ChatCompletionChunk]:
        etype = _get(event, "type")
        if etype == "message_start":
            message = _get(event, "message")
            self.id = _get(message, "id") or self.id  # adopt the real message id
            self.input_tokens = _get(_get(message, "usage"), "input_tokens", 0) or 0
            return [self._chunk(delta=Delta(role="assistant"), finish_reason=None)]
        if etype == "content_block_delta":
            delta = _get(event, "delta")
            if _get(delta, "type") == "text_delta":
                text = _get(delta, "text", "") or ""
                if text:
                    return [self._chunk(delta=Delta(content=text), finish_reason=None)]
            return []
        if etype == "message_delta":
            self.stop_reason = _get(_get(event, "delta"), "stop_reason", self.stop_reason)
            usage = _get(event, "usage")
            if usage is not None:
                self.output_tokens = _get(usage, "output_tokens", self.output_tokens) or 0
            return []
        if etype == "message_stop":
            out = [self._chunk(delta=Delta(), finish_reason=map_finish_reason(self.stop_reason))]
            if self.include_usage:
                out.append(
                    self._chunk(
                        delta=None,
                        finish_reason=None,
                        choices=[],
                        usage=Usage(
                            prompt_tokens=self.input_tokens,
                            completion_tokens=self.output_tokens,
                            total_tokens=self.input_tokens + self.output_tokens,
                        ),
                    )
                )
            return out
        return []


def translate_stream_events(
    events, *, chunk_id: str, created: int, model: str, include_usage: bool = False
) -> list[ChatCompletionChunk]:
    """Drive ``StreamTranslator`` over a sync iterable of events (for tests)."""
    state = StreamTranslator(chunk_id, created, model, include_usage=include_usage)
    out: list[ChatCompletionChunk] = []
    for event in events:
        out.extend(state.handle(event))
    return out


# --------------------------------------------------------------------------- #
# Error mapping — pure, duck-typed on ``status_code`` so it is testable with
# plain fake exceptions (no SDK import). Messages are generic so no key/internal
# detail leaks to the client.
# --------------------------------------------------------------------------- #
# status -> (openai type, code, client-facing message)
_STATUS_MAP = {
    401: ("authentication_error", "upstream_authentication", "upstream authentication failed"),
    403: ("permission_error", "upstream_permission_denied", "upstream permission denied"),
    404: ("not_found_error", "upstream_model_not_found", "upstream model not found"),
    400: ("invalid_request_error", "upstream_invalid_request", "upstream rejected the request"),
}


def _retry_after(exc: Any) -> str | None:
    headers = getattr(getattr(exc, "response", None), "headers", None)
    if headers is None:
        return None
    try:
        return headers.get("retry-after")
    except AttributeError:
        return None


def map_anthropic_error(exc: Any) -> UpstreamProviderError:
    """Map a (duck-typed) Anthropic SDK exception to an ``UpstreamProviderError``.

    Reads only ``status_code`` and ``response.headers`` (never isinstance on SDK
    classes), so it is testable with fakes. Catch-all: any unmapped status (e.g.
    413) or a 5xx becomes a 502; timeouts a 504; connection errors a 502."""
    status = getattr(exc, "status_code", None)

    if status is None:  # no HTTP status -> timeout / connection / unknown
        name = type(exc).__name__.lower()
        if "timeout" in name:
            return UpstreamProviderError(
                "upstream request timed out",
                status_code=504,
                type="api_error",
                code="upstream_timeout",
            )
        if "connection" in name:
            return UpstreamProviderError(
                "could not reach the upstream provider",
                status_code=502,
                type="api_error",
                code="upstream_unavailable",
            )
        return UpstreamProviderError(
            "upstream provider error", status_code=502, type="api_error", code="upstream_error"
        )

    if status == 429:
        retry_after = _retry_after(exc)
        message = "upstream rate limit exceeded"
        if retry_after:
            message += f" (retry after {retry_after}s)"
        return UpstreamProviderError(
            message, status_code=429, type="rate_limit_error", code="rate_limit_exceeded"
        )

    if status in _STATUS_MAP:
        type_, code, message = _STATUS_MAP[status]
        return UpstreamProviderError(message, status_code=status, type=type_, code=code)

    # catch-all: any other status (413, 422, 5xx, ...) -> 502 Bad Gateway
    return UpstreamProviderError(
        "upstream provider error", status_code=502, type="api_error", code="upstream_error"
    )
