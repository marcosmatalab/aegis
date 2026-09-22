# Governance evidence (F8)

`aegis evidence` generates a **partial technical evidence** document mapping the real artifacts Aegis already produces to specific framework controls. It is **not a compliance certificate** — it is auto-generated from system data, it maps only the small set of technical controls below, and the majority of each framework's **underlying clauses** are explicitly out of scope (so the control counts are not a coverage percentage).

> **The crux:** every control's status is **derived from a real artifact field at generation time**, never hand-written. No artifact → the control is `not_covered` (with the exact command to produce it), never "compliant" with invented text. `measured`/`estimated` is earned only from real telemetry; the golden loader refuses a hand-authored report that claims it.

**Four statuses** per control: `covered` (a first-class real measurement backs it) · `partial` (real value, but the control's full intent exceeds it — carries a caveat) · `not_covered` (the artifact is absent / the live posture is off) · `out_of_scope` (Aegis structurally can't evidence it — the majority).

**What backs what (real sources):**

| Evidence | Real source | Controls (with verified ids) |
|---|---|---|
| Accuracy / V&V | `eval-<suite>.json` (CLEAR + L1/L2/L3) | Art.15(1)/(3), NIST **MEASURE 2.3**, ISO **A.6.2.4** |
| Reliability | same (`clear.reliability`) | NIST **MEASURE 2.5** |
| Robustness / adversarial | `redteam-<suite>.json` (detection rate + **named gaps**) | Art.15(4), NIST **MEASURE 2.7** |
| Safety (output toxicity / PII only, **partial**) | `redteam-<suite>.json` (toxicity + PII-leak categories) | NIST **MEASURE 2.6** |
| Measurement validity | `calibration.json` (Cohen's κ) | NIST **MEASURE 2.13** |
| Input/output posture | **effective config** (guardrail flags) | Art.15(5), ISO **A.6.2.6** |
| Request event logs | effective config (`AEGIS_OTEL_ENABLED`) | ISO **A.6.2.8** |

**Honesty gates** (enforced in the pure builder, tested): a `mock` judge caps eval controls at `partial` (it's a wiring smoke test); an undefined Cohen's κ is `not_covered`, never a stale "almost perfect"; guardrails-off renders the posture control `not_covered` (the real OFF state, reported honestly); the guardrail posture (config *now*) and the red-team report are **separate** controls, since the posture is not necessarily the config the red-team report ran under. **Out of scope** (stated up front): EU AI Act Arts. 9/10/12/13/14; NIST GOVERN/MAP/MANAGE; ISO 42001 management-system controls (A.2–A.5, A.7–A.10).

```bash
pip install -e ".[reporting]"                 # fpdf2 (pure-Python, offline, no system libs)
aegis evidence --eval reports/eval-golden.json --output reports/evidence.pdf
aegis evidence --format json --output reports/evidence.json   # JSON sidecar; needs no fpdf2
```

> Framework provenance: NIST MEASURE **ids** are verbatim from NIST AI 100-1 (titles abbreviated/paraphrased); EU AI Act Art.15 paragraph numbering via the official-text aggregators; ISO/IEC 42001 Annex A ids/titles are paraphrased from public listings (the standard is paywalled) — each control row records its `verified_via` source. Anthropic's v1.38 cache-token span attributes are a noted future enhancement, not yet implemented.

---

---

[← back to the README](../README.md)
