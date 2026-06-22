"""Upstream provider abstraction and the deterministic MockProvider.

F1 ships ONLY the keyless, fully deterministic ``MockProvider`` — no network, no
randomness, no wall-clock — so the gateway can be built and tested without API
keys. ``build_provider`` is the extension point for real providers: the planned
primary is **Anthropic (Claude)**, with **OpenAI** and **Gemini** as additional
options. Their SDKs are intentionally NOT imported in F1; when added they must be
lazy-imported inside their own branch so paid dependencies never load by default.
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

from aegis.gateway.config import Settings, get_settings
from aegis.gateway.errors import ProviderNotConfiguredError
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

_N_CONTENT_CHUNKS = 4  # fixed -> deterministic chunk count regardless of length


# --------------------------------------------------------------------------- #
# Deterministic pure helpers (module-level -> independently unit-testable)
# --------------------------------------------------------------------------- #
def _content_to_text(content: str | list[dict[str, Any]] | None) -> str:
    """Flatten message content (str / multimodal parts / None) to plain text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = (part.get("text", "") for part in content if isinstance(part, dict))
    return " ".join(p for p in parts if p).strip()


def _canonical_request_key(request: ChatCompletionRequest) -> str:
    """Stable JSON key over the parts that determine the mock's answer."""
    payload = {
        "model": request.model,
        "messages": [
            {"role": m.role, "content": _content_to_text(m.content)} for m in request.messages
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _stable_hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _derive_id(h: str) -> str:
    return f"chatcmpl-{h[:24]}"


def _derive_created(h: str) -> int:
    # Deterministic pseudo-timestamp (NOT time.time()); ``or 1`` guarantees > 0.
    return int(h[:8], 16) or 1


def _count_tokens(text: str) -> int:
    return len(text.split())  # whitespace tokenizer; deterministic, no tiktoken


def _canned_answer(request: ChatCompletionRequest) -> str:
    for message in reversed(request.messages):
        if message.role == "user":
            text = _content_to_text(message.content)
            if text:
                return f"Echo: {text}"
    return "Hello! This is a deterministic mock response from Aegis."


def _split_into_deltas(text: str, n: int = _N_CONTENT_CHUNKS) -> list[str]:
    """Split text into at most ``n`` contiguous, non-empty slices.

    Reconstruction is lossless: ``"".join(_split_into_deltas(t)) == t``.
    """
    if not text:
        return []
    step = max(1, (len(text) + n - 1) // n)
    return [text[i : i + step] for i in range(0, len(text), step)]


# --------------------------------------------------------------------------- #
# Provider interface
# --------------------------------------------------------------------------- #
class Provider(ABC):
    """Abstract upstream. ``stream`` is implemented as an async generator."""

    name: str

    @abstractmethod
    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse: ...

    @abstractmethod
    def stream(self, request: ChatCompletionRequest) -> AsyncIterator[ChatCompletionChunk]: ...


class MockProvider(Provider):
    """Deterministic, keyless, offline provider. Identical request -> identical
    bytes (id/created/content) across calls and processes."""

    name = "mock"

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        h = _stable_hash(_canonical_request_key(request))
        answer = _canned_answer(request)
        prompt_tokens = sum(_count_tokens(_content_to_text(m.content)) for m in request.messages)
        completion_tokens = _count_tokens(answer)
        return ChatCompletionResponse(
            id=_derive_id(h),
            created=_derive_created(h),
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=ResponseMessage(role="assistant", content=answer),
                    finish_reason="stop",
                )
            ],
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )

    async def stream(self, request: ChatCompletionRequest) -> AsyncIterator[ChatCompletionChunk]:
        h = _stable_hash(_canonical_request_key(request))
        chunk_id = _derive_id(h)
        created = _derive_created(h)
        answer = _canned_answer(request)

        def _chunk(delta: Delta, finish_reason: str | None) -> ChatCompletionChunk:
            return ChatCompletionChunk(
                id=chunk_id,
                created=created,
                model=request.model,
                choices=[ChunkChoice(index=0, delta=delta, finish_reason=finish_reason)],
            )

        # 1) role-only delta, 2) content deltas, 3) terminal empty-delta + finish.
        yield _chunk(Delta(role="assistant"), None)
        for piece in _split_into_deltas(answer):
            yield _chunk(Delta(content=piece), None)
        yield _chunk(Delta(), "stop")


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
def build_provider(name: str, settings: Settings | None = None) -> Provider:
    """Provider factory used by the gateway dependency and tests.

    ``"mock"`` is the keyless default (``settings`` ignored). ``"anthropic"`` is a
    real adapter: its module is imported lazily here (so importing this module
    never pulls the optional SDK) and it reads the API key from ``settings`` —
    falling back to ``get_settings()`` when not provided. Missing key / missing
    SDK surface as a clean ``ProviderNotConfiguredError`` (never an ImportError).
    ``"openai"``/``"google"`` are still unwired.
    """
    if name == "mock":
        return MockProvider()
    if name == "anthropic":
        from aegis.gateway.providers.anthropic_provider import AnthropicProvider

        settings = settings or get_settings()
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            default_max_tokens=settings.anthropic_max_tokens,
            base_url=settings.anthropic_base_url,
            timeout=settings.anthropic_timeout_s,
        )
    raise ProviderNotConfiguredError(
        f"Provider {name!r} is not configured; available: 'mock', 'anthropic'. "
        "OpenAI and Gemini arrive in a later phase."
    )
