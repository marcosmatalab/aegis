# 🛡️ Aegis

> A reliability + security + governance gateway for LLMs and agents — an OpenAI-compatible proxy that sits *in front of* any model and adds input/output guardrails, three-level trajectory evals, OWASP-mapped automated red-teaming, OpenTelemetry observability, and a CI gate that fails the build when quality or safety regress.

> **⚠️ Status: under active construction (pre-alpha).** Working today: the OpenAI-compatible `/v1/chat/completions` proxy (F1) with SSE streaming; an input/output **guardrails** layer (F2); and a 3-level **eval engine** (F3) with a golden anchor set and an `aegis eval run` CLI. Everything is backed by a deterministic, keyless **mock provider / mock judge** (no real model wired yet). The planned primary real provider is **Anthropic (Claude)**, with OpenAI and Gemini as additional options. Red-team, the CI gate and governance land incrementally through the phased roadmap.

---

## Why

A single drop-in change (`base_url`) gives an existing app guardrails, tracing, and continuous evals — without touching its model or business logic. Aegis is not a model; it is the **control layer** around any model or agent.

The differentiator is **evaluation depth**: not just scoring the final output, but scoring the *trajectory* (every tool call, in order, recovering from errors), validating the LLM judge against human labels, and wiring it all into a CI gate so regressions block merges instead of reaching production.

---

## Architecture

```
   Client / App                ┌──────────────────────────────────────────────┐
   (OpenAI-compatible)  ──────▶ │                AEGIS GATEWAY                   │
   change base_url only         │     POST /v1/chat/completions (drop-in)        │
                                │                                                │
                                │   ┌──────────────┐         ┌──────────────┐    │
                                │   │   INPUT       │         │   OUTPUT      │   │
                                │   │  GUARDRAILS   │         │  GUARDRAILS   │   │
                                │   │ · injection   │         │ · PII         │   │
                                │   │ · PII         │         │ · toxicity    │   │
                                │   │ · policy      │         │ · schema      │   │
                                │   └──────┬───────┘         └──────▲───────┘    │
                                │          │                        │            │
                                │          ▼                        │            │
                                │     ┌────────────────────────────┴───┐        │
                                │     │   LLM / AGENT PROVIDER           │        │
                                │     │   (Claude / GPT / Gemini · …)    │        │
                                │     └────────────────┬─────────────────┘        │
                                │                      │ trace (OTel spans)       │
                                │                      ▼                          │
                                │          ┌──────────────────────────┐           │
                                │          │  OTel GenAI → Langfuse    │           │
                                │          └──────────────────────────┘           │
                                └──────────────────────────────────────────────┘
                                                  │
              ┌───────────────────────────────────┼───────────────────────────────────┐
              ▼                                    ▼                                    ▼
   ┌─────────────────────┐           ┌─────────────────────┐            ┌──────────────────────┐
   │     EVAL ENGINE      │           │   RED-TEAM ENGINE    │            │     GOVERNANCE        │
   │  L1 session  (goal)  │           │  OWASP LLM Top 10    │            │  AI Act Art.15 /      │
   │  L2 trace (quality)  │           │  + OWASP Agentic ASI │            │  NIST AI RMF /        │
   │  L3 tool (calls)     │           │  injection, hijack,  │            │  ISO/IEC 42001        │
   │  CoT / agent-judge   │           │  tool-misuse, leaks  │            │  → evidence PDF       │
   └──────────┬───────────┘           └──────────┬───────────┘            └──────────────────────┘
              └───────────────────────┬──────────┘
                                      ▼
                          ┌───────────────────────┐         ┌──────────────────────────┐
                          │   CI GATE (Actions)    │────────▶│   Dashboard (Next.js)     │
                          │  pass / fail + report  │         │  scorecards, trends, runs │
                          └───────────────────────┘         └──────────────────────────┘
```

**Flow:** `gateway → guardrails → provider → evals / red-team → CI gate`.

---

## Quickstart

> The `/health` probe and the `/v1/chat/completions` proxy (on the mock provider) run today. Guardrails, evals and red-team are on the roadmap.

```bash
# 1. Clone and enter
git clone git@github.com:marcosmatalab/aegis.git
cd aegis

# 2. Create a virtualenv and install (dev extras include pytest + ruff)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. Configure (optional — defaults to the keyless mock provider)
cp .env.example .env

# 4. Run the gateway
uvicorn aegis.gateway.main:app --reload --port 8080
curl http://localhost:8080/health  # -> {"status":"ok","version":"0.1.0"}

# 5. Call it like the OpenAI API (drop-in: point any client's base_url here)
curl http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"mock/echo-1","messages":[{"role":"user","content":"hello"}]}'
# Add "stream": true for an SSE stream of chat.completion.chunk frames.

# 6. Lint + test
ruff check .
ruff format --check .
pytest
```

---

## Roadmap (phased)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **F0** | Skeleton: packaging, CI, `/health` gateway | ✅ done |
| **F1** | OpenAI-compatible proxy (`/v1/chat/completions`): drop-in `base_url`, SSE streaming, deterministic mock provider, OpenAI error envelope | ✅ done |
| **F1.x** | OTel → Langfuse tracing of each request (observability) | ⬜ planned |
| **F2** | Input/output guardrails: prompt-injection scan (OWASP LLM01), PII redaction (regex default, Presidio optional), allow/deny policy, basic toxicity — off by default | ✅ done |
| **F3** | Evals L1 (session/goal) · L2 (trace/quality, G-Eval CoT) · L3 (tool correctness); golden set + `aegis eval run` + JSON report | ✅ done |
| **F4** | Trajectory metrics (TrajectoryAccuracy, ToolCorrectness, T-Eval) + CLEAR; Agent-as-a-Judge | ⬜ planned |
| **F5** | Judge calibration: human-labelled set + Cohen's κ reported | ⬜ planned |
| **F6** | Automated red-team mapped to OWASP LLM Top 10 + OWASP Agentic (ASI) | ⬜ planned |
| **F7** | CI gate: run evals + red-team per PR and **block merge** on regression | ⬜ planned |
| **F8** | Governance mapping (EU AI Act Art.15 / NIST AI RMF / ISO 42001) → evidence PDF | ⬜ planned |
| **F9** | Polished dashboard, trends, 2-min demo | ⬜ planned |

---

## Guardrails (F2)

A defense-in-depth layer around the proxy — cheap deterministic checks first, a costlier check only if needed. **Disabled by default** (`AEGIS_GUARDRAILS_ENABLED=false`): with it off, the gateway is a byte-identical F1 passthrough.

- **Input** — prompt-injection detection (deterministic patterns mapped to **OWASP LLM01**, tuned to avoid false positives on legitimate code/prose); **PII redaction** before the request reaches the provider (email, phone, credit card via Luhn, Spanish **DNI/NIE** via the mod-23 checksum); an allow/deny **policy** engine.
- **Output** — **PII-leak** detection (block or redact) and **basic** deterministic **toxicity** detection.
- **Blocking** returns a clean OpenAI error — HTTP 400, `type: "guardrail_blocked"`, with a `code` (`prompt_injection`, `policy_denied`, `pii_leak`, `toxicity`). This works in streaming too: input blocks are a normal JSON 400; output blocks emit a guardrail error frame (no `[DONE]`).
- **PII engine** — the deterministic regex engine is the default (no extra deps, CI-fast). **Microsoft Presidio** is an optional richer engine: `pip install -e ".[guardrails]"` and set `AEGIS_GR_PII_ENGINE=presidio` (also needs a spaCy model).

> **Streaming trade-off:** when output guardrails are active, the stream is buffered and scanned before any byte is sent (leak-safe), so streaming is effectively non-incremental in that mode. With output guardrails off, streaming is fully incremental as in F1.

Each toggle and threshold is configurable via `AEGIS_GR_*` settings (see [.env.example](.env.example)).

---

## Evals (F3)

A 3-level eval engine that runs fully **offline** over a hand-made golden anchor set:

- **L1 — session / goal** (deterministic, no LLM): the goal is met iff every required tool was called, every `must_include` keyword is present (as a whole word), and no `must_not_include` keyword appears.
- **L2 — trace / quality** (LLM-as-judge): relevancy (vs a reference) and faithfulness (vs context), scored by a **G-Eval / Chain-of-Thought** judge that reasons before scoring. The judge is abstracted behind an interface with a deterministic **MockJudge** (default), so the suite runs with no API keys; the real provider-backed judge and an ensemble are wired behind it.
- **L3 — tool** (deterministic, no LLM): tool-call correctness (right tool, right args, right order) via an F1 over exact matches plus an LCS order score.

Run it:

```bash
aegis eval run                       # scores the golden set with the mock judge
aegis eval run --suite ci --output reports/ci.json
# --fail-under is an inert CI-gate seam in F3; the real gate is F7.
```

> **Honesty (this matters):** the LLM-as-judge is treated as **directional** — a signal to validate against human labels (Cohen's κ, a later phase), **not ground truth**. L2 **faithfulness in the MockJudge is lexical containment, not entailment**: a reordered copy of the context scores 1.0 (there is a golden case, `reordered-copy-limitation`, that documents exactly this). What the project actually sells is that the **eval gate catches regressions**, not that any single judge is correct. The golden set interleaves passing and failing cases — including several where one level passes while another fails — to demonstrate L1/L2/L3 are independent.

---

## Tech stack

| Layer | Technology |
|-------|------------|
| API gateway | FastAPI + uvicorn (OpenAI-compatible endpoint) |
| Providers | `anthropic`, `openai`, `google-genai` (multi-provider) |
| Guardrails | Presidio (PII), injection/output scanners, optional safety classifier |
| Evals | G-Eval (CoT), trajectory metrics, Agent-as-a-Judge |
| Red-team | Synthetic attacks mapped to OWASP LLM + OWASP Agentic (ASI) |
| Observability | OpenTelemetry (GenAI semconv) → Langfuse |
| Persistence | PostgreSQL (runs, verdicts, cases) |
| Dashboard | Next.js + Tailwind + Recharts |
| CI | GitHub Actions (eval gate, report artifact, status check) |

---

## Honesty guardrails

This is a **portfolio project**, not a product with customers. Reported numbers are real measurements over the project's own golden set — no inflated claims. The LLM judge is treated as *directional* and validated against human labels (κ); the value proposition is that the **gate catches regressions**, not that any single judge is ground truth. Guardrails are defense-in-depth with coverage mapped to OWASP — not a claim of total detection.

---

## License

[MIT](LICENSE) © 2026 Marcos Mata García
