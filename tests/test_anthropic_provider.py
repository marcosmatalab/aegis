"""Tests for AnthropicProvider using an injected fake client (no SDK, no key)."""

from __future__ import annotations

import asyncio

import pytest

from aegis.gateway.errors import (
    ProviderNotConfiguredError,
    UnsupportedFeatureError,
    UpstreamProviderError,
)
from aegis.gateway.providers.anthropic_provider import (
    AnthropicProvider,
    _build_client,
    is_available,
)
from aegis.gateway.schemas import ChatCompletionRequest


# --- fakes ------------------------------------------------------------------ #
class _StatusError(Exception):
    def __init__(self, status_code):
        super().__init__("upstream boom")
        self.status_code = status_code


class _FakeMessages:
    def __init__(self, *, message=None, events=None, error=None):
        self._message = message
        self._events = events or []
        self._error = error
        self.calls: list[dict] = []

    async def create(self, **params):
        self.calls.append(params)
        if self._error is not None:
            raise self._error
        if params.get("stream"):
            events = self._events

            async def _gen():
                for event in events:
                    yield event

            return _gen()
        return self._message


class FakeAnthropic:
    def __init__(self, **kwargs):
        self.messages = _FakeMessages(**kwargs)


class _MidStreamFailMessages:
    """Yields some events, then raises mid-iteration (a realistic transport error
    on the real async stream, distinct from an error at create())."""

    def __init__(self, events, error):
        self._events = events
        self._error = error

    async def create(self, **params):
        events, error = self._events, self._error

        async def _gen():
            for event in events:
                yield event
            raise error

        return _gen()


class _MidStreamFailAnthropic:
    def __init__(self, events, error):
        self.messages = _MidStreamFailMessages(events, error)


_MSG = {
    "id": "msg_1",
    "content": [{"type": "text", "text": "Hi there"}],
    "stop_reason": "end_turn",
    "usage": {"input_tokens": 2, "output_tokens": 3},
}

_STREAM_EVENTS = [
    {"type": "message_start", "message": {"id": "msg_s", "usage": {"input_tokens": 4}}},
    {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi"}},
    {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 1}},
    {"type": "message_stop"},
]


def _req(**overrides) -> ChatCompletionRequest:
    body = {"model": "anthropic/claude-opus-4-8", "messages": [{"role": "user", "content": "hi"}]}
    body.update(overrides)
    return ChatCompletionRequest(**body)


def _provider(**fake_kwargs) -> AnthropicProvider:
    return AnthropicProvider(
        api_key="sk-test", default_max_tokens=77, client=FakeAnthropic(**fake_kwargs)
    )


def _collect(agen):
    async def _run():
        return [item async for item in agen]

    return asyncio.run(_run())


# --- construction ----------------------------------------------------------- #
def test_missing_key_raises_at_construction():
    with pytest.raises(ProviderNotConfiguredError):
        AnthropicProvider(api_key=None, default_max_tokens=10, client=FakeAnthropic())


def test_name_and_is_a_provider():
    from aegis.gateway.upstream import Provider

    prov = _provider(message=_MSG)
    assert prov.name == "anthropic"
    assert isinstance(prov, Provider)


# --- complete --------------------------------------------------------------- #
def test_complete_returns_openai_shape():
    prov = _provider(message=_MSG)
    resp = asyncio.run(prov.complete(_req()))
    assert resp.id == "msg_1"
    assert resp.model == "anthropic/claude-opus-4-8"  # original request model echoed
    assert resp.choices[0].message.content == "Hi there"
    assert resp.choices[0].finish_reason == "stop"
    assert resp.usage.total_tokens == 5


def test_complete_sends_translated_params():
    prov = _provider(message=_MSG)
    asyncio.run(prov.complete(_req(model="anthropic/claude-x", temperature=1.9)))
    sent = prov.client.messages.calls[0]
    assert sent["model"] == "claude-x"  # prefix stripped
    assert sent["max_tokens"] == 77  # provider default
    assert sent["temperature"] == 1.0  # clamped


def test_complete_maps_upstream_error():
    prov = _provider(error=_StatusError(429))
    with pytest.raises(UpstreamProviderError) as exc:
        asyncio.run(prov.complete(_req()))
    assert exc.value.status_code == 429


def test_complete_rejects_unsupported_before_calling_upstream():
    prov = _provider(message=_MSG)
    with pytest.raises(UnsupportedFeatureError):
        asyncio.run(prov.complete(_req(tools=[{"type": "function"}])))
    assert prov.client.messages.calls == []  # never reached the upstream


# --- stream ----------------------------------------------------------------- #
def test_stream_yields_role_content_and_terminal():
    prov = _provider(events=_STREAM_EVENTS)
    chunks = _collect(prov.stream(_req()))
    assert len(chunks) == 3  # exactly: role, content, terminal (no spurious chunks)
    assert chunks[0].choices[0].delta.role == "assistant"
    assert chunks[1].choices[0].delta.content == "Hi"
    assert chunks[-1].choices[0].finish_reason == "stop"  # from message_delta, not null
    assert {c.id for c in chunks} == {"msg_s"}  # adopted message id


def test_stream_passes_stream_flag():
    prov = _provider(events=_STREAM_EVENTS)
    _collect(prov.stream(_req()))
    assert prov.client.messages.calls[0]["stream"] is True


def test_stream_includes_usage_when_requested():
    prov = _provider(events=_STREAM_EVENTS)
    chunks = _collect(prov.stream(_req(stream_options={"include_usage": True})))
    # exactly one usage-bearing chunk, and it follows the terminal finish chunk
    assert sum(c.usage is not None for c in chunks) == 1
    assert chunks[-2].choices[0].finish_reason == "stop"
    last = chunks[-1]
    assert last.choices == []
    assert last.usage.prompt_tokens == 4
    assert last.usage.completion_tokens == 1


def test_stream_maps_upstream_error_at_create():
    prov = _provider(error=_StatusError(503))
    with pytest.raises(UpstreamProviderError) as exc:
        _collect(prov.stream(_req()))
    assert exc.value.status_code == 502  # 5xx -> 502 Bad Gateway


def test_stream_maps_upstream_error_raised_mid_iteration():
    # an error surfacing AFTER >=1 event was yielded is remapped too (a distinct
    # path from an error at create()) -> still an UpstreamProviderError
    events = [{"type": "message_start", "message": {"id": "m", "usage": {"input_tokens": 1}}}]
    prov = AnthropicProvider(
        api_key="sk-test",
        default_max_tokens=10,
        client=_MidStreamFailAnthropic(events, _StatusError(503)),
    )
    with pytest.raises(UpstreamProviderError) as exc:
        _collect(prov.stream(_req()))
    assert exc.value.status_code == 502


# --- aclose (close the underlying client) ----------------------------------- #
class _CoroCloseClient:
    """Mirrors anthropic 0.85.0 AsyncAnthropic: a coroutine close(), no aclose."""

    def __init__(self):
        self.closes = 0

    async def close(self):
        self.closes += 1


class _AcloseClient:
    """Mirrors httpx.AsyncClient: an aclose() coroutine (preferred over close)."""

    def __init__(self):
        self.acloses = 0

    async def aclose(self):
        self.acloses += 1


class _SyncCloseClient:
    def __init__(self):
        self.closes = 0

    def close(self):  # non-awaitable close
        self.closes += 1


def test_aclose_closes_built_client_and_is_idempotent():
    fake = _CoroCloseClient()
    prov = AnthropicProvider(api_key="sk-test", default_max_tokens=10, client=fake)
    asyncio.run(prov.aclose())
    assert fake.closes == 1
    assert prov._client is None
    # second call is a clean no-op (client already cleared)
    asyncio.run(prov.aclose())
    assert fake.closes == 1


def test_aclose_prefers_aclose_over_close():
    fake = _AcloseClient()
    prov = AnthropicProvider(api_key="sk-test", default_max_tokens=10, client=fake)
    asyncio.run(prov.aclose())
    assert fake.acloses == 1


def test_aclose_handles_sync_close():
    fake = _SyncCloseClient()
    prov = AnthropicProvider(api_key="sk-test", default_max_tokens=10, client=fake)
    asyncio.run(prov.aclose())
    assert fake.closes == 1


def test_aclose_is_noop_when_client_never_built():
    prov = AnthropicProvider(api_key="sk-test", default_max_tokens=10)  # client lazy, unbuilt
    asyncio.run(prov.aclose())  # must not raise and must not force a build
    assert prov._client is None


# --- lazy SDK guard --------------------------------------------------------- #
@pytest.mark.skipif(is_available(), reason="anthropic SDK is installed in this environment")
def test_build_client_raises_clean_error_without_sdk():
    # With the SDK absent (the CI default), building a real client is a clean
    # ProviderNotConfiguredError pointing at the extra — never an ImportError.
    with pytest.raises(ProviderNotConfiguredError) as exc:
        _build_client("sk-test", None, 60.0)
    assert "anthropic" in str(exc.value).lower()
