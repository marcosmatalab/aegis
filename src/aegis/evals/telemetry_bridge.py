"""Bridge a real runtime GenAI span into a CLEAR ``CaseTrace`` (F1.x).

This is the ONLY honest way a CaseTrace earns non-synthetic provenance: from REAL
telemetry, not a hand-authored number. The gateway emits a span per request
(``gateway/telemetry``); this module turns a finished span (or its raw usage +
duration) into a ``CaseTrace`` where:

* ``latency_ms`` is the span's wall-clock duration -> ``latency_source="measured"``
  (a genuine measurement, even for the mock — though the committed offline suite
  never records one);
* ``cost_usd`` is real tokens x the static price table -> ``cost_source="estimated"``
  ONLY when the model is priced and tokens are present; the mock / unpriced models
  yield no cost (so they can never produce an estimated cost).

The resulting trace is a RUNTIME artifact: because its provenance is non-synthetic,
the golden loader refuses to read it from a file (see ``dataset.load_golden``) — it
exists only in-memory for a recorded-from-real-telemetry case.
"""

from __future__ import annotations

from typing import Any

from aegis.evals.models import CaseTrace
from aegis.evals.pricing import price_usd
from aegis.gateway.telemetry import (
    GEN_AI_REQUEST_MODEL,
    GEN_AI_RESPONSE_MODEL,
    GEN_AI_USAGE_INPUT_TOKENS,
    GEN_AI_USAGE_OUTPUT_TOKENS,
)

_NS_PER_MS = 1_000_000.0


def build_measured_trace(
    *,
    model: str,
    latency_ms: float,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> CaseTrace:
    """Build a CaseTrace from real telemetry.

    Latency is always ``measured`` (it is a real span duration). Cost is ``estimated``
    only when the model is priced AND both token counts are present; otherwise no cost
    is recorded (an unpriced model — including the mock — never gets an estimated
    cost, and a usage-less stream gets measured latency with no cost).
    """
    cost: float | None = None
    cost_source = "synthetic"  # never surfaces while cost_usd is None
    if prompt_tokens is not None and completion_tokens is not None:
        cost = price_usd(model, prompt_tokens, completion_tokens)
        if cost is not None:
            cost_source = "estimated"
    return CaseTrace(
        latency_ms=latency_ms,
        cost_usd=cost,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_source="measured",
        cost_source=cost_source,
    )


def trace_from_span(span: Any) -> CaseTrace:
    """Build a measured CaseTrace from a finished OTel span (a ReadableSpan).

    Reads the GenAI attributes the proxy set + the span's own start/end time. Prefers
    the response model (what actually answered) over the request model for pricing.
    """
    attrs = span.attributes or {}
    model = attrs.get(GEN_AI_RESPONSE_MODEL) or attrs.get(GEN_AI_REQUEST_MODEL) or ""
    latency_ms = (span.end_time - span.start_time) / _NS_PER_MS
    return build_measured_trace(
        model=model,
        latency_ms=latency_ms,
        prompt_tokens=attrs.get(GEN_AI_USAGE_INPUT_TOKENS),
        completion_tokens=attrs.get(GEN_AI_USAGE_OUTPUT_TOKENS),
    )
