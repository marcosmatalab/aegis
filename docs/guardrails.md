# Guardrails (F2)

A defense-in-depth layer around the proxy — cheap deterministic checks first, a costlier check only if needed. **Disabled by default** (`AEGIS_GUARDRAILS_ENABLED=false`): with it off, the gateway is a byte-identical F1 passthrough.

- **Input** — prompt-injection detection (deterministic patterns mapped to **OWASP LLM01**, tuned to avoid false positives on legitimate code/prose); **PII redaction** before the request reaches the provider (email, phone, credit card via Luhn, Spanish **DNI/NIE** via the mod-23 checksum); an allow/deny **policy** engine.
- **Output** — **PII-leak** detection (block or redact) and **basic** deterministic **toxicity** detection.
- **Blocking** returns a clean OpenAI error — HTTP 400, `type: "guardrail_blocked"`, with a `code` (`prompt_injection`, `policy_denied`, `pii_leak`, `toxicity`). This works in streaming too: input blocks are a normal JSON 400; output blocks emit a guardrail error frame (no `[DONE]`).
- **PII engine** — the deterministic regex engine is the default (no extra deps, CI-fast). **Microsoft Presidio** is an optional richer engine: `pip install -e ".[guardrails]"` and set `AEGIS_GR_PII_ENGINE=presidio` (also needs a spaCy model).

> **Streaming trade-off:** when output guardrails are active, the stream is buffered and scanned before any byte is sent (leak-safe), so streaming is effectively non-incremental in that mode. With output guardrails off, streaming is fully incremental as in F1.

Each toggle and threshold is configurable via `AEGIS_GR_*` settings (see [.env.example](../.env.example)).

---

---

[← back to the README](../README.md)
