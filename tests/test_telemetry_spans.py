"""F1.x GenAI spans over /v1/chat/completions — fully offline (in-memory exporter).

Real spans are asserted via OTel's InMemorySpanExporter wired explicitly here (no
collector, no network). The provider is installed on ``app.state.tracer_provider``
AFTER the lifespan (which leaves it None by default), so these tests turn tracing
on without any env. The disabled path is proven byte-identical with zero spans.
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from aegis.gateway.errors import UpstreamProviderError
from aegis.gateway.main import app
from aegis.gateway.proxy import _sse_generator, get_provider
from aegis.gateway.schemas import ChatCompletionRequest
from aegis.gateway.upstream import MockProvider, Provider


def _memory_tracing():
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter, provider


def _payload(**over):
    body = {"model": "mock/echo-1", "messages": [{"role": "user", "content": "ping"}]}
    body.update(over)
    return body


def test_nonstream_span_carries_genai_metadata():
    exporter, provider = _memory_tracing()
    app.dependency_overrides[get_provider] = lambda: MockProvider()
    try:
        with TestClient(app) as client:
            app.state.tracer_provider = provider
            resp = client.post("/v1/chat/completions", json=_payload())
            spans = exporter.get_finished_spans()
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert len(spans) == 1
    s = spans[0]
    assert s.name == "chat mock/echo-1"  # {operation} {model}
    a = s.attributes
    assert a["gen_ai.operation.name"] == "chat"
    assert a["gen_ai.request.model"] == "mock/echo-1"
    assert a["gen_ai.provider.name"] == "mock"  # NOT the old gen_ai.system
    assert a["gen_ai.response.model"] == "mock/echo-1"
    assert a["gen_ai.usage.input_tokens"] == 1  # "ping"
    assert a["gen_ai.usage.output_tokens"] == 2  # "Echo: ping"
    assert tuple(a["gen_ai.response.finish_reasons"]) == ("stop",)
    # PRIVACY: metadata only — no message content leaked into the span
    assert not any(("messages" in k) or ("prompt" in k) or ("completion" in k) for k in a)


def test_disabled_is_byte_identical_and_emits_no_spans():
    exporter, provider = _memory_tracing()
    app.dependency_overrides[get_provider] = lambda: MockProvider()
    try:
        with TestClient(app) as client:
            app.state.tracer_provider = None  # disabled (the default)
            off = client.post("/v1/chat/completions", json=_payload())
            assert exporter.get_finished_spans() == ()  # no provider wired => nothing
            app.state.tracer_provider = provider  # enabled
            on = client.post("/v1/chat/completions", json=_payload())
            assert len(exporter.get_finished_spans()) == 1
    finally:
        app.dependency_overrides.clear()

    assert off.status_code == on.status_code == 200
    assert off.content == on.content  # the span never alters the response bytes


def test_stream_span_spans_the_whole_generation():
    exporter, provider = _memory_tracing()
    app.dependency_overrides[get_provider] = lambda: MockProvider()
    try:
        with TestClient(app) as client:
            app.state.tracer_provider = provider
            resp = client.post("/v1/chat/completions", json=_payload(stream=True))
            assert resp.status_code == 200
            _ = resp.text  # consume the full SSE so the generator's finally runs
            spans = exporter.get_finished_spans()
    finally:
        app.dependency_overrides.clear()

    assert len(spans) == 1
    s = spans[0]
    assert s.name == "chat mock/echo-1"
    assert s.end_time is not None and s.end_time >= s.start_time  # real duration
    assert s.attributes["gen_ai.provider.name"] == "mock"
    assert tuple(s.attributes["gen_ai.response.finish_reasons"]) == ("stop",)


class _StreamBoom(Provider):
    """A provider whose stream() raises before yielding (mid-stream upstream error)."""

    name = "boom"

    async def complete(self, request):  # pragma: no cover - stream-only test
        raise UpstreamProviderError("unused", status_code=502, type="api_error")

    async def stream(self, request):
        raise UpstreamProviderError("boom upstream", status_code=502, type="api_error")
        yield  # makes this an async generator (never reached)


def test_stream_error_sets_span_error_status_and_records_exception():
    from opentelemetry.trace import StatusCode

    exporter, provider = _memory_tracing()
    app.dependency_overrides[get_provider] = lambda: _StreamBoom()
    try:
        with TestClient(app) as client:
            app.state.tracer_provider = provider
            resp = client.post("/v1/chat/completions", json=_payload(stream=True))
            _ = resp.text  # error frame, no [DONE]
            spans = exporter.get_finished_spans()
    finally:
        app.dependency_overrides.clear()

    assert len(spans) == 1  # span still ended despite the swallowed error
    s = spans[0]
    assert s.status.status_code == StatusCode.ERROR
    assert any(e.name == "exception" for e in s.events)


def test_sse_generator_ends_span_exactly_once_on_client_disconnect():
    # Drive the generator directly and aclose() it mid-stream (a client disconnect):
    # the manual span must still be ended exactly once via the finally.
    ends = {"n": 0}

    class _FakeSpan:
        def set_attribute(self, *a, **k): ...
        def record_exception(self, *a, **k): ...
        def set_status(self, *a, **k): ...
        def end(self):
            ends["n"] += 1

    async def _run():
        req = ChatCompletionRequest(
            model="mock/echo-1", messages=[{"role": "user", "content": "hi"}]
        )
        gen = _sse_generator(MockProvider(), req, span=_FakeSpan())
        await gen.__anext__()  # pull the first frame...
        await gen.aclose()  # ...then disconnect mid-stream

    asyncio.run(_run())
    assert ends["n"] == 1
