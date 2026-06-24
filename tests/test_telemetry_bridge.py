"""F1.x telemetry bridge: a REAL span becomes a measured/estimated CaseTrace, and
end-to-end that flows through run_suite into CLEAR — fully offline (no collector).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from aegis.evals.judge.agent import MockTrajectoryJudge
from aegis.evals.judge.mock import MockJudge
from aegis.evals.models import CandidateOutput, EvalCase, ExpectedVerdict
from aegis.evals.runner import run_suite
from aegis.evals.telemetry_bridge import build_measured_trace, trace_from_span
from aegis.gateway.main import app
from aegis.gateway.proxy import get_provider
from aegis.gateway.schemas import (
    ChatCompletionChunk,
    ChatCompletionResponse,
    Choice,
    ResponseMessage,
    Usage,
)
from aegis.gateway.upstream import Provider


# --- build_measured_trace (pure) -------------------------------------------- #
def test_priced_model_gets_measured_latency_and_estimated_cost():
    t = build_measured_trace(
        model="anthropic/claude-opus-4-8",
        latency_ms=123.4,
        prompt_tokens=1000,
        completion_tokens=1000,
    )
    assert t.latency_source == "measured" and t.latency_ms == 123.4
    assert t.cost_source == "estimated" and t.cost_usd == 0.09


def test_mock_model_gets_measured_latency_but_no_cost():
    # latency over the mock IS a real measurement; cost is NOT (no price) — never faked
    t = build_measured_trace(
        model="mock/echo-1", latency_ms=5.0, prompt_tokens=3, completion_tokens=4
    )
    assert t.latency_source == "measured"
    assert t.cost_usd is None and t.cost_source == "synthetic"


def test_missing_tokens_yield_no_cost():
    t = build_measured_trace(model="anthropic/claude-opus-4-8", latency_ms=10.0)
    assert t.latency_source == "measured" and t.cost_usd is None


# --- end-to-end: real span -> bridge -> run_suite -> CLEAR ------------------- #
class _FakeRealProvider(Provider):
    """A non-mock provider returning a priced model id + real usage (offline fake)."""

    name = "anthropic"

    async def complete(self, request) -> ChatCompletionResponse:
        return ChatCompletionResponse(
            id="chatcmpl-real",
            created=1,
            model="anthropic/claude-opus-4-8",
            choices=[
                Choice(
                    index=0,
                    message=ResponseMessage(role="assistant", content="hello there"),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=1000, completion_tokens=1000, total_tokens=2000),
        )

    async def stream(self, request) -> AsyncIterator[ChatCompletionChunk]:  # pragma: no cover
        raise NotImplementedError
        yield


def _memory_tracing():
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return exporter, provider


def test_real_span_bridges_to_clear_measured_and_estimated():
    exporter, provider = _memory_tracing()
    app.dependency_overrides[get_provider] = lambda: _FakeRealProvider()
    try:
        with TestClient(app) as client:
            app.state.tracer_provider = provider
            resp = client.post(
                "/v1/chat/completions",
                json={
                    "model": "anthropic/claude-opus-4-8",
                    "messages": [{"role": "user", "content": "hi"}],
                },
            )
            assert resp.status_code == 200
            spans = exporter.get_finished_spans()
    finally:
        app.dependency_overrides.clear()

    assert len(spans) == 1
    trace = trace_from_span(spans[0])
    assert trace.latency_source == "measured"
    assert trace.cost_source == "estimated" and trace.cost_usd == 0.09

    # feed the recorded REAL trace through the offline runner -> CLEAR reports it
    case = EvalCase(
        id="recorded-real",
        user_goal="g",
        input_messages=[{"role": "user", "content": "hi"}],
        actual=CandidateOutput(final_output="hello there"),
        expected=ExpectedVerdict(l1_goal_met=True, l3_trajectory_match=True),
        trace=trace,
    )
    report = run_suite([case], MockJudge(), MockTrajectoryJudge(), suite="rt", created=0)
    assert report.clear["latency"]["status"] == "measured"
    assert report.clear["cost"]["status"] == "estimated"
