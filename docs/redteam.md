# Automated red-team (F6)

`aegis redteam run` runs a committed, versioned catalog of synthetic attacks (`src/aegis/redteam/datasets/attacks.jsonl`) **directly against the F2 guardrail pipeline** — fully offline, deterministic, keyless, no model and no network. It reuses `GuardrailPipeline.check_input` / `check_output` exactly as the proxy does, classifies each attack's `GuardrailResult` as **blocked** / **redacted** / **passed**, and reports a per-category **detection rate**.

**Result** — one run over 25 attacks (every row's expectation is pinned to real pipeline behaviour by a self-consistency test):

| Bucket | OWASP 2025 | detection | passed |
|---|---|---|---|
| `prompt_injection` | LLM01 | 7/11 (0.636) | 4 |
| `system_prompt_leak` | LLM07 | 3/3 (1.000) | 0 |
| `pii_input` | LLM02 | 3/4 (0.750) | 1 |
| `pii_output` | LLM02 | 2/3 (0.667) | 1 |
| `output_toxicity` | *content-safety — no clean OWASP slot* | 1/2 (0.500) | 1 |
| `policy_denylist` | *config-driven policy — not OWASP* | 2/2 (1.000) | 0 |
| **overall** | | **18/25 (0.720)** | **7** |

How to read this honestly — it is **coverage-against-this-catalog, NOT total security**:
- **Only the categories the F2 guardrails genuinely exercise are mapped.** `prompt_injection`→**LLM01**; `system_prompt_leak`→**LLM07** (the *same* injection detector and the *same* `prompt_injection` code as LLM01 — disclosed, not two detectors); PII in/out→**LLM02** (split by vector). Output toxicity is a tiny lexicon with **no clean OWASP-2025 slot**, and the policy bucket is a **config-driven content deny-list** (an illustrative bundled fixture, *not* a production policy and *not* OWASP LLM06 Excessive Agency). The OWASP edition is **2025**.
- **A passing attack is a surfaced finding, not a hidden failure.** The catalog deliberately ships payloads the regex/lexicon scanners are KNOWN to miss — leetspeak override, injection in the non-scanned `system`/`assistant`/`developer` roles, an obfuscated email, a glued-digit credit card, sub-threshold toxicity — so the detection rate is a real number below 100% with **every gap named** in the report's `known_gaps`. A `passed` row that is not a flagged gap fails to load.
- **Not covered (and why):** **ASI02 tool-misuse / ASI03 identity** — Aegis is a stateless text proxy that runs no agent loop and executes no tools; the guardrails inspect only flattened text, and tool/multimodal parts (forwarded at intake under `extra="allow"`) are rejected by the real Anthropic adapter (`ensure_text_only`, 400) — so there is no tool execution or agent trajectory to attack; **LLM05** (Improper Output Handling = downstream XSS/SQLi/code-exec) — no downstream renderer/executor; **LLM03/04/08/09/10** — no training/supply-chain, agency, or quota surface here; non-English coverage beyond the shipped Spanish variants is a known gap. ASI01 goal-hijack is disclosed only as an *overlap* on injection rows.
- **It REPORTS; it does not gate.** The runner returns typed findings in the *same shape* as the eval gate's regressions (`kind` / `scope` / `detail`), so a future `aegis gate` can union them additively — but F6 builds **no** red-team gate, no baseline, and exits 0 by default (an opt-in `--fail-under-detection` floor is off unless passed). Red-team *gating* is a later phase; this is why F7 stays partial.

---

---

[← back to the README](../README.md)
