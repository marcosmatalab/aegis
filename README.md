# 🛡️ Aegis

> A reliability + security + governance gateway for LLMs and agents — an OpenAI-compatible proxy that sits *in front of* any model and adds input/output guardrails, three-level trajectory evals, OWASP-mapped automated red-teaming, OpenTelemetry observability, and a CI gate that fails the build when quality or safety regress.

> **⚠️ Status: under active construction (pre-alpha).** This repository currently contains only the project skeleton and a minimal gateway. The components below describe the target design; each lands incrementally through the phased roadmap.

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

> The minimal gateway (a `/health` endpoint) runs today. Everything else is on the roadmap.

```bash
# 1. Clone and enter
git clone git@github.com:marcosmatalab/aegis.git
cd aegis

# 2. Create a virtualenv and install (dev extras include pytest + ruff)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# 3. Configure
cp .env.example .env               # fill in provider keys when proxying lands

# 4. Run the gateway
uvicorn aegis.gateway.main:app --reload --port 8080
curl http://localhost:8080/health  # -> {"status":"ok","version":"0.1.0"}

# 5. Lint + test
ruff check .
pytest
```

---

## Roadmap (phased)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **F0** | Skeleton: packaging, CI, `/health` gateway | 🟡 in progress |
| **F1** | OpenAI-compatible proxy (`/v1/chat/completions`) with streaming + OTel → Langfuse tracing | ⬜ planned |
| **F2** | Input/output guardrails: prompt-injection scan, PII (Presidio), toxicity, schema | ⬜ planned |
| **F3** | Evals L1 (session/goal) · L2 (trace/quality, G-Eval CoT) · L3 (tool correctness); persist verdicts | ⬜ planned |
| **F4** | Trajectory metrics (TrajectoryAccuracy, ToolCorrectness, T-Eval) + CLEAR; Agent-as-a-Judge | ⬜ planned |
| **F5** | Judge calibration: human-labelled set + Cohen's κ reported | ⬜ planned |
| **F6** | Automated red-team mapped to OWASP LLM Top 10 + OWASP Agentic (ASI) | ⬜ planned |
| **F7** | CI gate: run evals + red-team per PR and **block merge** on regression | ⬜ planned |
| **F8** | Governance mapping (EU AI Act Art.15 / NIST AI RMF / ISO 42001) → evidence PDF | ⬜ planned |
| **F9** | Polished dashboard, trends, 2-min demo | ⬜ planned |

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
