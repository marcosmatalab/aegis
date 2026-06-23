"""Real Anthropic (Claude) provider — the ONLY module that imports the SDK.

The ``anthropic`` SDK is an optional extra, imported LAZILY inside ``_build_client``
so importing this module (and the gateway) never loads it; the deterministic mock
runs with no SDK installed. The provider accepts an injected ``client`` (any object
exposing ``messages.create``), so every unit test runs offline with a fake — no
SDK, no API key, no network. All wire-shape translation is delegated to the pure
``anthropic_translate`` module.

Scope is TEXT completions (see ``anthropic_translate`` for the documented
divergences and the 400 rejection of tool-calling / non-text content).
"""

from __future__ import annotations

import importlib.util
import inspect
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from aegis.gateway.errors import ProviderNotConfiguredError
from aegis.gateway.providers import anthropic_translate as tr
from aegis.gateway.schemas import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
)
from aegis.gateway.upstream import Provider

log = logging.getLogger("aegis.gateway")


def is_available() -> bool:
    """True if the optional ``anthropic`` SDK is importable (never imports it)."""
    return importlib.util.find_spec("anthropic") is not None


def _build_client(api_key: str, base_url: str | None, timeout: float) -> Any:
    """Lazily construct a real ``AsyncAnthropic`` client (the sole SDK import)."""
    if not is_available():
        raise ProviderNotConfiguredError(
            "The 'anthropic' SDK is not installed. Install it with: pip install -e \".[anthropic]\""
        )
    from anthropic import AsyncAnthropic

    kwargs: dict[str, Any] = {"api_key": api_key, "timeout": timeout}
    if base_url:
        kwargs["base_url"] = base_url
    return AsyncAnthropic(**kwargs)


def _wants_usage(request: ChatCompletionRequest) -> bool:
    """OpenAI ``stream_options.include_usage`` (kept via the schema's extra=allow)."""
    options = getattr(request, "stream_options", None)
    if isinstance(options, dict):
        return bool(options.get("include_usage"))
    return bool(getattr(options, "include_usage", False))


class AnthropicProvider(Provider):
    """Forwards OpenAI-format chat completions to the Anthropic Messages API."""

    name = "anthropic"

    def __init__(
        self,
        *,
        api_key: str | None,
        default_max_tokens: int,
        base_url: str | None = None,
        timeout: float = 60.0,
        client: Any = None,
    ):
        if not api_key:
            raise ProviderNotConfiguredError(
                "Provider 'anthropic' selected but ANTHROPIC_API_KEY is not set."
            )
        self._api_key = api_key
        self._default_max_tokens = default_max_tokens
        self._base_url = base_url
        self._timeout = timeout
        self._client = client  # injected in tests; built lazily otherwise

    @property
    def client(self) -> Any:
        if self._client is None:
            self._client = _build_client(self._api_key, self._base_url, self._timeout)
        return self._client

    def _mapped(self, exc: Exception) -> Exception:
        # Log only the exception class (never the message/key); return the mapped
        # OpenAI-envelope error for the client.
        log.warning("anthropic call failed: %s", type(exc).__name__)
        return tr.map_anthropic_error(exc)

    async def complete(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        # to_anthropic_params may raise UnsupportedFeatureError (a clean 400);
        # that is a request error, raised BEFORE the upstream call, so it is not
        # remapped as an upstream failure.
        params = tr.to_anthropic_params(request, self._default_max_tokens)
        try:
            message = await self.client.messages.create(**params)
        except Exception as exc:
            raise self._mapped(exc) from exc
        return tr.from_anthropic_message(message, request.model)

    async def stream(self, request: ChatCompletionRequest) -> AsyncIterator[ChatCompletionChunk]:
        params = tr.to_anthropic_params(request, self._default_max_tokens)
        translator = tr.StreamTranslator(
            "chatcmpl-anthropic",
            int(time.time()),
            request.model,
            include_usage=_wants_usage(request),
        )
        try:
            stream = await self.client.messages.create(**params, stream=True)
            async for event in stream:
                for chunk in translator.handle(event):
                    yield chunk
        except Exception as exc:
            raise self._mapped(exc) from exc

    async def aclose(self) -> None:
        """Close the underlying client (its httpx pool) if one was built.

        Idempotent and a no-op when the client was never created (never force a
        lazy build just to close it). Duck-types ``aclose`` then ``close`` — the
        anthropic SDK exposes a coroutine ``close()``, httpx uses ``aclose()`` —
        and awaits the result only if it is awaitable. ``self._client`` is cleared
        BEFORE awaiting so a concurrent/second call is a clean no-op.
        """
        client = self._client
        if client is None:
            return
        self._client = None
        closer = getattr(client, "aclose", None) or getattr(client, "close", None)
        if closer is None:
            return
        result = closer()
        if inspect.isawaitable(result):
            await result
