# Observability — OpenTelemetry tracing (F1.x)

The gateway emits **one OpenTelemetry span per `/v1/chat/completions` request**, following the **GenAI semantic conventions (~v1.38)**. Attributes are `gen_ai.operation.name` (`chat`), `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.provider.name` (the attribute that superseded `gen_ai.system`), and `gen_ai.usage.input_tokens` / `output_tokens`; the span name is `chat {model}` and its wall-clock duration is the gateway's first real request timing.

> **Young convention, pinned + disclosed.** The GenAI semconv moved to its own repo, [`open-telemetry/semantic-conventions-genai`](https://github.com/open-telemetry/semantic-conventions-genai), and is **still evolving** — client spans left *experimental* in early 2026 but parts of the spans spec remain "Development" and `OTEL_SEMCONV_STABILITY_OPT_IN` exists. Aegis pins the attribute keys as its own string constants (so a package bump can't break it) and discloses the version in the module docstring.

- **Opt-in, no-op by default.** `AEGIS_OTEL_ENABLED=false` (default) installs no `TracerProvider` and the proxy is a **byte-identical F1/F2 passthrough** — no span, no timing, no SDK import (the `[otel]` extra need not even be installed). This mirrors the `guardrails_enabled` posture. A monkeypatched-absent test proves the no-op branch even though CI installs OTel.
- **Exporter needs no collector.** `AEGIS_OTEL_EXPORTER=none` (default when enabled) creates + attributes spans but exports nowhere — tests assert on them via an in-memory exporter, so **CI is green offline**. `console` writes to stderr for local debugging; `otlp` (→ an OTLP collector or **Langfuse**) is lazy-imported behind the `[otel]` extra and reads `OTEL_EXPORTER_OTLP_ENDPOINT`, using a `BatchSpanProcessor` so a stalled collector never adds latency to a request.
- **Privacy default (ties into F2).** Spans carry **metadata only** — model, token counts, duration. **No message content** (`gen_ai.input.messages` / `output.messages`; `gen_ai.prompt` / `completion` are deprecated) is ever captured, because dumping prompt/response text into telemetry would re-leak the very PII the F2 guardrails strip. Content capture is not implemented; any future capture would be an explicit, documented, off-by-default opt-in.

**This is what turns CLEAR honest about Cost/Latency.** A real request span is bridged into a `CaseTrace` (`evals/telemetry_bridge`): the span's duration is a **measured** Latency, and real tokens × a **static list price** (`evals/pricing.py`) is an **estimated** Cost (an estimate, not a measurement — hence the distinct status). The mock and any unpriced model have no price-table entry, so they can **never** produce a cost; and `measured`/`estimated` provenance is set only by this runtime bridge — the golden loader **rejects** a hand-authored file that claims it. Anthropic's v1.38 cache-token attributes are a noted future enhancement, not yet implemented.

```bash
# Trace to stderr locally (mock provider, no collector needed):
AEGIS_OTEL_ENABLED=true AEGIS_OTEL_EXPORTER=console \
  uvicorn aegis.gateway.main:app --port 8080
# Export to an OTLP collector / Langfuse (needs the [otel] extra + an endpoint):
pip install -e ".[otel]"
AEGIS_OTEL_ENABLED=true AEGIS_OTEL_EXPORTER=otlp \
  OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318 \
  uvicorn aegis.gateway.main:app --port 8080
```

---

---

[← back to the README](../README.md)
