"""F1.x telemetry seam: opt-in TracerProvider, no-op default, exporter factory.

Pure unit tests for the seam itself (no HTTP). The OTel SDK is present in [dev], so
the enabled paths run offline with no collector; the SDK-absent branch is FORCE-
simulated by monkeypatching ``otel_available`` so it is exercised even in CI (which
installs the SDK). Nothing here touches the global TracerProvider.
"""

from __future__ import annotations

import pytest

from aegis.gateway import telemetry as tel
from aegis.gateway.config import Settings


def _settings(**kw) -> Settings:
    return Settings(_env_file=None, **kw)


def test_setup_returns_none_when_disabled():
    assert tel.setup_tracing(_settings(otel_enabled=False)) is None


def test_setup_returns_none_when_sdk_absent(monkeypatch):
    # FORCE the absent-SDK branch even though [dev] installs the SDK — this is the
    # branch guaranteeing "byte-identical when OTel is not installed".
    monkeypatch.setattr(tel, "otel_available", lambda: False)
    assert tel.setup_tracing(_settings(otel_enabled=True, otel_exporter="none")) is None


def test_setup_builds_provider_when_enabled_none_exporter():
    provider = tel.setup_tracing(_settings(otel_enabled=True, otel_exporter="none"))
    assert provider is not None
    # a real tracer with the span API the proxy uses
    tracer = tel.get_tracer(provider)
    span = tracer.start_span("chat mock/echo-1")
    span.set_attribute(tel.GEN_AI_OPERATION_NAME, tel.OPERATION_CHAT)
    span.end()
    tel.shutdown_tracing(provider)


def test_setup_console_exporter_builds_provider():
    provider = tel.setup_tracing(_settings(otel_enabled=True, otel_exporter="console"))
    assert provider is not None
    tel.shutdown_tracing(provider)


def test_setup_otlp_without_package_raises_clean_error(monkeypatch):
    monkeypatch.setattr(tel, "_otlp_available", lambda: False)
    with pytest.raises(tel.TelemetryConfigError) as exc:
        tel.setup_tracing(_settings(otel_enabled=True, otel_exporter="otlp"))
    assert "[otel]" in str(exc.value)  # actionable install hint, never a raw ImportError


def test_get_tracer_none_is_noop_and_safe():
    tracer = tel.get_tracer(None)
    # both span entrypoints the proxy uses must no-op without raising
    with tracer.start_as_current_span("chat x") as span:
        span.set_attribute(tel.GEN_AI_REQUEST_MODEL, "x")
        span.record_exception(RuntimeError("boom"))
        span.set_status("error")
    manual = tracer.start_span("chat x")
    manual.set_attribute(tel.GEN_AI_USAGE_INPUT_TOKENS, 3)
    manual.end()


def test_setup_does_not_touch_the_global_tracer_provider():
    from opentelemetry import trace

    before = trace.get_tracer_provider()
    provider = tel.setup_tracing(_settings(otel_enabled=True, otel_exporter="none"))
    after = trace.get_tracer_provider()
    assert after is before  # we never call set_tracer_provider
    assert provider is not after  # the gateway owns its OWN provider, not the global
    tel.shutdown_tracing(provider)


def test_shutdown_none_is_noop():
    tel.shutdown_tracing(None)  # must not raise


def test_shutdown_invokes_provider_shutdown():
    class _Spy:
        closed = False

        def shutdown(self) -> None:
            self.closed = True

    spy = _Spy()
    tel.shutdown_tracing(spy)
    assert spy.closed is True
