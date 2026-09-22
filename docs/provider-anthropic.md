# Real provider — Anthropic / Claude

The gateway can forward to **real Claude** behind the same `Provider` interface as the mock. The `anthropic` SDK is an **optional extra**, lazy-imported only when selected, so the default install and CI stay keyless and SDK-free.

```bash
pip install -e ".[anthropic]"          # install the optional SDK
export ANTHROPIC_API_KEY=sk-ant-...    # key is read from the env only, never hardcoded/logged
export AEGIS_DEFAULT_PROVIDER=anthropic
uvicorn aegis.gateway.main:app --port 8080
# Now any OpenAI client pointed at this base_url talks to Claude. The leading
# "anthropic/" in a model id is stripped (e.g. "anthropic/claude-opus-4-8").
```

**What the adapter covers (be honest about the edges):**

- ✅ **Text** chat completions, **non-streaming and streaming (SSE)** — OpenAI→Anthropic request translation (system/developer messages hoisted into the top-level `system`, `max_tokens` defaulted since Anthropic requires it, `stop`/`temperature`/`top_p`) and Anthropic→OpenAI response translation (text, `usage`, `stop_reason`→`finish_reason`, model echo).
- ⚠️ **Text only for now.** **Tool-calling** and **non-text multimodal** (images) are **not translated yet** — a request using them is **rejected** with a clean `400 invalid_request_error` (`code: unsupported_by_provider`) rather than silently dropped. **Tool-calling is the tracked next phase**, not an open-ended deferral.
- **Streaming:** `finish_reason` is taken from Anthropic's `message_delta` event (not `message_stop`) so it is never null. A usage chunk is emitted only when the request sets `stream_options.include_usage` (OpenAI's contract). A failure mid-stream surfaces as an SSE error frame (the HTTP 200 is already committed), carrying the mapped `type`/`code`; no `[DONE]` follows.

**Documented divergences from OpenAI:**

- `temperature` is **clamped to [0, 1]** (Anthropic's max is 1; OpenAI allows 2) — a value like `1.5` is accepted and capped rather than erroring — **and omitted entirely (along with `top_p`/`top_k`) for models that reject sampling params: Opus 4.7+, all Opus 5.x, and unknown newer Opus (which default to omit, conservatively)**. Those models return `400 temperature is deprecated for this model` otherwise; per Anthropic guidance you drop the field and let the model's default sampling apply (reasoning control on 4.8 is `effort` + adaptive thinking, not temperature). Sonnet/Haiku, Opus 4.6-and-earlier, and the legacy `claude-3-opus-*` keep the clamp.
- `created` is a synthesized wall-clock timestamp (Anthropic does not return one), so the real-provider path is **not** byte-deterministic like the mock.
- An unrecognized `stop_reason` falls back to `finish_reason: "stop"`.

**Error mapping** (upstream failure → OpenAI envelope; messages are generic so no key/internals leak):

| Anthropic | HTTP | `type` | `code` |
|---|---|---|---|
| 401 | 401 | `authentication_error` | `upstream_authentication` |
| 403 | 403 | `permission_error` | `upstream_permission_denied` |
| 404 | 404 | `not_found_error` | `upstream_model_not_found` |
| 429 (+`Retry-After`) | 429 | `rate_limit_error` | `rate_limit_exceeded` |
| 400 | 400 | `invalid_request_error` | `upstream_invalid_request` |
| any other (e.g. 413) / 5xx | **502** | `api_error` | `upstream_error` |
| timeout | **504** | `api_error` | `upstream_timeout` |
| connection | **502** | `api_error` | `upstream_unavailable` |

Selecting `anthropic` with **no key** or **without the SDK installed** is a clean `provider_not_configured` (HTTP 500) — never an `ImportError`. The whole adapter is unit-tested offline with a fake client (no key, no SDK, no network); one **skippable live test** runs only when `ANTHROPIC_API_KEY` is set and the SDK is installed.

**Client lifecycle.** The real provider owns a network client (an httpx connection pool), so it is built **once per process** — cached on `app.state` and reused across requests behind an `asyncio` lock (so concurrent first-requests can't race two clients into existence) — and **closed cleanly on shutdown** via the FastAPI lifespan. Construction stays lazy (on the first request, never at startup), so an `anthropic`-with-no-key boot is still a 500 *response* rather than a startup crash. The keyless mock holds no resources and is unaffected.

---

---

[← back to the README](../README.md)
