"""F1.x OpenTelemetry tracing seam for the gateway — opt-in, no-op by default.

This module NEVER imports ``opentelemetry`` at load time: every SDK import is lazy,
inside a function, guarded by :func:`otel_available` (``importlib.util.find_spec``)
exactly like the optional Anthropic SDK in ``anthropic_provider``. So importing the
gateway with the ``[otel]`` extra absent is safe, and with ``AEGIS_OTEL_ENABLED``
off the gateway is a byte-identical F1 passthrough.

The gateway OWNS its ``TracerProvider`` on ``app.state`` (built once in the
lifespan, mirroring the provider cache) — we deliberately do NOT call the global
``trace.set_tracer_provider`` (a set-once process global that would leak across
tests and other apps in the same process).

GenAI semantic conventions
---------------------------
Attribute keys follow the OpenTelemetry **GenAI semantic conventions ~v1.38**, which
now live in their own repo (``open-telemetry/semantic-conventions-genai``; the old
``opentelemetry.io/docs/specs/semconv/gen-ai/`` pages show "moved"). These
conventions are YOUNG / still evolving: GenAI client spans left *experimental* in
early 2026, but parts of the spans spec remain "Development" and
``OTEL_SEMCONV_STABILITY_OPT_IN`` exists. We hardcode the key STRINGS below (rather
than import the churn-prone experimental constants module) so a semconv package bump
can never break import; ``gen_ai.provider.name`` is the attribute that superseded the
older ``gen_ai.system``.

PRIVACY: spans carry METADATA ONLY (model, token counts, duration). NO message
content (``gen_ai.input.messages`` / ``gen_ai.output.messages``; ``gen_ai.prompt`` /
``gen_ai.completion`` are deprecated anyway) — dumping prompt/response text into
telemetry would re-leak the very PII the F2 guardrails strip. Content capture is not
implemented; any future capture would be an explicit, documented, off-by-default
opt-in.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from contextlib import contextmanager
from typing import Any

from aegis.gateway.config import Settings

log = logging.getLogger("aegis.telemetry")

# --- GenAI semconv attribute keys (own strings; see module docstring) -------- #
GEN_AI_OPERATION_NAME = "gen_ai.operation.name"
GEN_AI_PROVIDER_NAME = "gen_ai.provider.name"  # supersedes the older gen_ai.system
GEN_AI_REQUEST_MODEL = "gen_ai.request.model"
GEN_AI_RESPONSE_MODEL = "gen_ai.response.model"
GEN_AI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GEN_AI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GEN_AI_RESPONSE_FINISH_REASONS = "gen_ai.response.finish_reasons"
# Aegis-namespaced derived attributes — explicitly NOT semconv keys.
AEGIS_COST_USD = "aegis.cost.usd"
AEGIS_COST_SOURCE = "aegis.cost.source"

OPERATION_CHAT = "chat"
SERVICE_NAME = "aegis-gateway"
_INSTRUMENTATION_SCOPE = "aegis.gateway"
# Probe the exact submodule that _build_span_processor imports (not just the parent
# package), so a partial install still yields a clean TelemetryConfigError, not a raw
# ImportError.
_OTLP_HTTP_MODULE = "opentelemetry.exporter.otlp.proto.http.trace_exporter"


class TelemetryConfigError(RuntimeError):
    """Raised when OTel is enabled with an exporter whose package is not installed."""


def otel_available() -> bool:
    """True if the OpenTelemetry SDK is importable (never imports it)."""
    return importlib.util.find_spec("opentelemetry") is not None


def _otlp_available() -> bool:
    """True if the optional OTLP/proto-http exporter is importable (never imports it)."""
    return importlib.util.find_spec(_OTLP_HTTP_MODULE) is not None


# --------------------------------------------------------------------------- #
# Import-free no-op tracer/span — used whenever tracing is disabled or absent.
# Supports the exact surface the proxy uses (start_span + start_as_current_span +
# set_attribute / record_exception / set_status / end) so callers never branch.
# --------------------------------------------------------------------------- #
class _NoOpSpan:
    def set_attribute(self, *args: Any, **kwargs: Any) -> None: ...
    def record_exception(self, *args: Any, **kwargs: Any) -> None: ...
    def set_status(self, *args: Any, **kwargs: Any) -> None: ...
    def end(self, *args: Any, **kwargs: Any) -> None: ...
    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


class _NoOpTracer:
    def start_span(self, *args: Any, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()

    @contextmanager
    def start_as_current_span(self, *args: Any, **kwargs: Any):
        yield _NoOpSpan()


_NOOP_TRACER = _NoOpTracer()


def _build_span_processor(exporter: str) -> Any | None:
    """Build the span processor for ``exporter``; None for the no-export 'none'.

    Always BatchSpanProcessor (async, bounded) on the export paths so a stalled
    collector can never add latency to a user request. ConsoleSpanExporter writes
    to STDERR (never stdout, which the CLI uses). 'otlp' lazy-imports the optional
    exporter and raises a clean :class:`TelemetryConfigError` when it is absent.
    """
    if exporter == "none":
        return None
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    if exporter == "console":
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter

        return BatchSpanProcessor(ConsoleSpanExporter(out=sys.stderr))
    if exporter == "otlp":
        if not _otlp_available():
            raise TelemetryConfigError(
                "AEGIS_OTEL_EXPORTER='otlp' needs the OTLP exporter; install it with: "
                'pip install -e ".[otel]"'
            )
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        return BatchSpanProcessor(OTLPSpanExporter())
    return None  # unreachable: otel_exporter is Literal-validated upstream


def setup_tracing(settings: Settings) -> Any | None:
    """Build and return a ``TracerProvider`` when tracing is enabled, else ``None``.

    No global state is touched — the caller stores the returned provider on
    ``app.state`` and passes it back to :func:`get_tracer`. Returns ``None`` when the
    master switch is off OR the SDK is absent (logged, never raised — a missing extra
    must not crash startup). Raises :class:`TelemetryConfigError` only when an
    exporter is explicitly selected whose package is missing.
    """
    if not settings.otel_enabled:
        return None
    if not otel_available():
        log.warning(
            "AEGIS_OTEL_ENABLED is true but the opentelemetry SDK is not installed; "
            'tracing stays off. Install it with: pip install -e ".[otel]"'
        )
        return None
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE_NAME}))
    processor = _build_span_processor(settings.otel_exporter)
    if processor is not None:
        provider.add_span_processor(processor)
    return provider


def get_tracer(provider: Any | None) -> Any:
    """Return a tracer from ``provider``, or the import-free no-op when ``None``."""
    if provider is None:
        return _NOOP_TRACER
    return provider.get_tracer(_INSTRUMENTATION_SCOPE)


def shutdown_tracing(provider: Any | None) -> None:
    """Flush + close the provider's span processors. No-op when never set up."""
    if provider is None:
        return
    provider.shutdown()


# --------------------------------------------------------------------------- #
# Span attribute helpers — called by the proxy so it never imports opentelemetry.
# `span` duck-types set_attribute/record_exception/set_status (a real span or the
# no-op span). METADATA ONLY: no message content is ever read or set here.
# --------------------------------------------------------------------------- #
def span_name(model: str) -> str:
    """GenAI span name convention: ``{operation} {model}``."""
    return f"{OPERATION_CHAT} {model}"


def set_request_attributes(span: Any, *, model: str, provider_name: str) -> None:
    span.set_attribute(GEN_AI_OPERATION_NAME, OPERATION_CHAT)
    span.set_attribute(GEN_AI_REQUEST_MODEL, model)
    span.set_attribute(GEN_AI_PROVIDER_NAME, provider_name)


def set_response_attributes(
    span: Any,
    *,
    model: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    finish_reason: str | None = None,
) -> None:
    """Set whichever response attrs are available; omit the rest (never fabricate).

    Streaming providers that emit no terminal usage chunk (the mock; Anthropic
    without ``include_usage``) simply leave the token attrs unset — honest, not zero.
    """
    if model:
        span.set_attribute(GEN_AI_RESPONSE_MODEL, model)
    if prompt_tokens is not None:
        span.set_attribute(GEN_AI_USAGE_INPUT_TOKENS, prompt_tokens)
    if completion_tokens is not None:
        span.set_attribute(GEN_AI_USAGE_OUTPUT_TOKENS, completion_tokens)
    if finish_reason:
        span.set_attribute(GEN_AI_RESPONSE_FINISH_REASONS, [finish_reason])


def mark_span_error(span: Any, exc: BaseException) -> None:
    """Record an exception + set ERROR status on the streaming path.

    The streaming generators swallow-and-return, so the context manager's auto-
    recording (which the non-stream path relies on) never fires — hence the explicit
    call here, keeping both paths consistent. ``span.record_exception(exc)`` emits an
    ``exception`` event carrying ``exception.type``, ``exception.message`` (= str(exc))
    and ``exception.stacktrace``; the status description is the exception type only.
    The recorded message is the provider/AegisError string (e.g. an upstream
    rate-limit), NEVER LLM prompt/response content — so no message text reaches the
    span (consistent with the metadata-only privacy posture)."""
    span.record_exception(exc)
    if not otel_available():
        return
    from opentelemetry.trace import Status, StatusCode

    span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
