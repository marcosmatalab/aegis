# Roadmap (phased)

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **F0** | Skeleton: packaging, CI, `/health` gateway | ✅ done |
| **F1** | OpenAI-compatible proxy (`/v1/chat/completions`): drop-in `base_url`, SSE streaming, deterministic mock provider, OpenAI error envelope | ✅ done |
| **F1.x** | OpenTelemetry GenAI-semconv tracing of each request (opt-in, no-op default); CLEAR Latency→measured / Cost→estimated from real spans; OTLP/Langfuse optional | ✅ done |
| **F2** | Input/output guardrails: prompt-injection scan (OWASP LLM01), PII redaction (regex default, Presidio optional), allow/deny policy, basic toxicity — off by default | ✅ done |
| **F3** | Evals L1 (session/goal) · L2 (trace/quality, G-Eval CoT) · L3 (tool correctness); golden set + `aegis eval run` + JSON report | ✅ done |
| **F4** | Trajectory metrics (TrajectoryAccuracy, ToolCorrectness, Progress Rate, T-Eval) + CLEAR; Agent-as-a-Judge | ✅ done |
| **F5** | Judge calibration: hand-labelled set + Cohen's κ (per criterion + global) via `aegis calibrate` | ✅ done |
| **F6** | Automated red-team: committed attack catalog vs the F2 guardrails, per-OWASP-category detection rate (`aegis redteam run`) | ✅ done |
| **F7** | CI gate: run **evals and the red-team catalog** per PR and **block merge** on regression vs committed baselines (`aegis eval gate`, `aegis redteam gate`) | ✅ done |
| **F8** | Governance evidence: map real eval/red-team/calibration artifacts + config to EU AI Act Art.15 / NIST MEASURE / ISO 42001 controls → `aegis evidence` PDF (partial technical evidence) | ✅ done |
| **F9** | Read-only dashboard (Next.js + Recharts) over the real reports — scorecards, trends, caveats verbatim (`dashboard/`); end-to-end demo (`scripts/demo.sh` → `docs/demo.gif`, [DEMO.md](../DEMO.md)) | ✅ done |

---

---

[← back to the README](../README.md)
