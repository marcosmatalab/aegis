# Evals, trajectory metrics and judge calibration (F3–F5)

The full detail behind the eval stack: the three scoring levels, the trajectory
metrics and CLEAR dimensions, and how the judge was calibrated against human
labels. The headline figures and the commands that reproduce them are on the
[front page](../README.md).

## Evals (F3)

A 3-level eval engine that runs fully **offline** over a hand-made golden anchor set:

- **L1 — session / goal** (deterministic, no LLM): the goal is met iff every required tool was called, every `must_include` keyword is present (as a whole word), and no `must_not_include` keyword appears.
- **L2 — trace / quality** (LLM-as-judge): relevancy (vs a reference) and faithfulness (vs context), scored by a **G-Eval-inspired** judge that reasons briefly before scoring. The judge is abstracted behind an interface with a deterministic **MockJudge** (default), so the suite runs with no API keys; a **real** judge that reuses the Anthropic provider (the single cached client) and an ensemble are wired behind it (`AEGIS_JUDGE_BACKEND=geval|ensemble`).
- **L3 — tool** (deterministic, no LLM): tool-call correctness (right tool, right args, right order) via an F1 over exact matches plus an LCS order score.

Run it:

```bash
aegis eval run                       # scores the golden set with the mock judge
aegis eval run --suite ci --output reports/ci.json
# --fail-under is a manual absolute-floor seam; the real baseline-comparing
# gate is `aegis eval gate` (F7) — see "CI regression gate (F7)" below.
```

> **Honesty (this matters):** the LLM-as-judge is treated as **directional** — a signal validated against human labels (Cohen's κ — now implemented, see [Judge calibration (F5)](evals.md#judge-calibration-f5)), **not ground truth**. The MockJudge is **purely lexical**: relevancy is token overlap and L2 **faithfulness is lexical containment, not entailment** — a reordered copy of the context scores 1.0 (see the golden case `reordered-copy-limitation`), and every deterministic L2 "pass" is therefore a lexical match (verbatim / permuted / subset), never a rewarded paraphrase. L3's order check is over tool *names*, so duplicate same-tool calls are order-insensitive (documented in the scorer). What the project actually sells is that the **eval gate catches regressions**, not that any single judge is correct. The golden set interleaves passing and failing cases — including several where one level passes while another fails — to demonstrate L1/L2/L3 are independent.

> **The real judge is G-Eval-*inspired*, not canonical.** It uses light Chain-of-Thought (justify, then score) but reads the score **directly** from a compact JSON reply — it does **not** do canonical G-Eval's logprob-weighted scoring, because the Anthropic API exposes no per-token logprobs. The honest consequence is **more variance** than logprob G-Eval, which is why it runs at **temperature 0** and why **judge calibration (Cohen's κ vs human labels) is now implemented** ([F5](evals.md#judge-calibration-f5)) — the score is still directional, not ground truth. A messy or truncated reply **never crashes the eval**: it falls back to a **neutral 0.5 flagged `parse_failed`**, surfaced in the L2 breakdown of the persisted report so a degradation is auditable (note: a neutral 0.5 *passes* the diagnostic L2 threshold, so the flag — not the score — is what tells you the judge didn't really measure). The real judge is exercised by injected fakes offline plus **one gated, skippable live test** (a single low-`max_tokens` call); the bulk suite stays on the keyless MockJudge.

---
## Trajectory metrics, CLEAR & Agent-as-a-Judge (F4)

F4 adds richer, mostly-deterministic **trajectory** scoring on top of L3, a per-run **CLEAR** scorecard, and an **Agent-as-a-Judge** that evaluates the *process* — all offline, surfaced in the same `aegis eval run` report.

**Trajectory metrics** (each 0..1, computed over the golden trajectory; they share L3's matcher):

| Metric | What it measures | Distinct from |
|--------|------------------|---------------|
| **ToolCorrectness** | F1 over exact (name+args) matches, order-insensitive | the order-sensitive metrics below |
| **TrajectoryAccuracy** | similarity of the whole path to the golden path — LCS over full steps, normalized by the longer sequence (tolerant of insertions) | T-Eval (which is strict positional) |
| **Progress Rate** | AgentBoard-style fraction of **milestones** (subgoals) reached, **order-independent**; milestones are explicit or derived from the expected tools | survives reordering, unlike Trajectory/T-Eval |
| **T-Eval** | step-by-step planning: is the call at each **position** the expected one? strict positional match, so one early insertion penalizes every later step | TrajectoryAccuracy (which realigns via subsequence) |

**CLEAR** (five dimensions per run) — and an explicit table of each dimension's `status`, which is honest about *how* the number was obtained:

| Dimension | Status | How it's computed |
|-----------|--------|-------------------|
| **Accuracy** | ✅ measured | mean of the per-level eval scores (the suite `overall`) |
| **Efficiency** | ✅ measured | useful (exact) tool calls / total calls — penalizes redundant, extra, wrong-args calls |
| **Reliability** | ✅ measured (proxy) | end-to-end success rate (all applicable levels pass); cross-run flakiness deferred to F5+ |
| **Latency** | 📈 **measured** *with real telemetry* | the request span's wall-clock duration (F1.x); **synthetic** from hand-authored `trace.latency_ms`, **placeholder** with no trace |
| **Cost** | 🧮 **estimated** *with real telemetry* | real measured tokens × a **static list price** (`evals/pricing.py`) — an estimate, not a measurement; **synthetic** from hand-authored `trace.cost_usd`, **placeholder** with no trace / unpriced model |

The four statuses — `measured`, `estimated`, `synthetic`, `placeholder` — ride in the JSON report and the CLI summary (only `measured` renders without a suffix), so a list-price estimate is never mistaken for a real measurement and a hand-authored number is never mistaken for either. **`measured`/`estimated` are reached ONLY when real telemetry flows through the F1.x bridge** (see [Observability](observability.md)); the committed mock suite has no real telemetry, so `aegis eval run` over the golden set stays `placeholder`/`synthetic`. The basis string discloses the traced denominator (e.g. `1/32 traced cases`), and a mixed-provenance suite honestly **downgrades to `synthetic`** rather than letting one real case launder the rest. Cost/Latency only get a normalized 0..1 score when an optional budget/SLO (`AEGIS_CLEAR_COST_BUDGET_USD` / `AEGIS_CLEAR_LATENCY_BUDGET_MS`) is set.

**Agent-as-a-Judge** evaluates the trajectory itself — **loops**, **redundant steps**, and **error recovery** (via each call's `status`). It reuses F3's judge *pattern* (an async ABC + a deterministic mock + a clearly-stubbed real backend) but not F3's output-centric `Judge` interface.

> **Honesty (same line as F3):** the `MockTrajectoryJudge` is an **illustrative heuristic, not a semantic judge** — it flags loops/redundancy by **literal pattern matching** over the recorded calls and infers recovery from the `status` field, with **fixed, arbitrary penalty weights** (so tests can assert exact numbers). It does not understand whether a step was *reasonable*. The real reasoning-LLM `agent` backend is a clear stub here. As with the F3 judge, the value is a **regression-catching signal**, not ground truth.

---
## Judge calibration (F5)

How much does the real (G-Eval-inspired) judge agree with a human? `aegis calibrate` scores the configured judge over a **hand-labelled set of 30 cases** (15 relevancy + 15 faithfulness, `src/aegis/evals/datasets/calibration.jsonl`) and reports **Cohen's κ** — observed agreement corrected for chance — **per criterion and global**, alongside the raw agreement `p_o` and the full confusion matrix, into a gitignored `reports/` JSON.

**Result** — one run, judge frozen (`claude-opus-4-8`, temperature dropped per the Opus 4.7+ rule, `max_tokens=1024`), 0 parse failures over all 30 cases:

| Scope | Cohen's κ | p_o | n | confusion (HpJp / HpJf / HfJp / HfJf) |
|---|---|---|---|---|
| Global | 0.933 | 0.967 | 30 | 13 / 0 / 1 / 16 |
| Relevancy | 0.865 | 0.933 | 15 | 6 / 0 / 1 / 8 |
| Faithfulness | 1.000 | 1.000 | 15 | 7 / 0 / 0 / 8 |

Rows = human, cols = judge, positive class = `pass` (HpJp = human-pass/judge-pass, etc.).

**That table is not a claim — it is a committed artifact.** The run's 30 per-case verdicts
live in [`artifacts/calibration-geval-2026-09-22.jsonl`](../artifacts/calibration-geval-2026-09-22.jsonl),
so anyone recomputes the number in about a second with **no API key, no `[anthropic]` extra
and no network**:

```bash
aegis calibrate --from-verdicts artifacts/calibration-geval-2026-09-22.jsonl
# global: kappa=0.933 p_o=0.967 n_valid=30 parse_failed=0 band=almost perfect
```

`compute_calibration` is a pure function over a verdict list, so freezing the verdicts is
enough to freeze the number. `tests/test_evals_calibration_artifact.py` re-derives all three
κ values from that file on every CI run, which is what stops this table and the artifact from
drifting apart. Provenance, caveats and the regeneration procedure:
[`artifacts/README.md`](../artifacts/README.md).

How to read this honestly — it is **not** "the judge is 93% correct":
- **Directional, wide CI.** N=30, single annotator: one flipped label moves κ by ~0.06–0.13, so this is a directional signal, not a precise constant.
- **Optimistic upper bound.** The calibration set was authored and labelled within the same model family as the judge, on mostly unambiguous cases. Agreement on clear cases is cheap; on independent, messy production traffic it would likely be lower. This is a ceiling, not a field estimate.
- **The single disagreement is the finding, and it is now named.** Exactly one case diverges (global `HfJp = 1`, in relevancy): the judge *passed* a case the human failed. There are **zero** false-fails (`HpJf = 0` in every scope), so the judge's only observed error mode here is **over-approval** — it skews permissive, not strict. Because the verdicts are persisted, the case is recoverable: it is **`cal-rel-05`**, where the output appends *"and is visible from the Moon with the naked eye"* to a correct reference. The judge scored it **exactly `0.5`** and its reasoning names the false claim correctly — so the disagreement is the `>= 0.5` binarization rounding a deliberately *partial* score toward pass, not the judge misreading the case. That distinction is only visible because the per-case verdicts are kept.

As everywhere else: the judge is a **directional** signal validated against human labels, not ground truth — what the gate ultimately enforces is regression-catching, not judge correctness.

```bash
aegis calibrate --from-verdicts artifacts/calibration-geval-2026-09-22.jsonl
                                    # the real number, recomputed offline — no key, no network
aegis calibrate --judge geval       # a fresh real run: needs ANTHROPIC_API_KEY + the [anthropic] extra
        --dump-verdicts artifacts/calibration-geval-$(date +%F).jsonl   # ... and freeze it
aegis calibrate --judge mock        # offline wiring smoke test only (see below)
```

κ binarizes the judge's continuous score at the **operative 0.5 threshold** (`>= 0.5` → pass) and compares it to the human pass/fail label, over the 2×2 table `κ = (p_o − p_e) / (1 − p_e)`.

**Read the number honestly — this is calibrated to be modest, not impressive:**

- **κ is DIRECTIONAL, not a quality verdict.** It measures *agreement with one annotator applying the rubric*, never ground truth — the value proposition stays "the gate catches regressions".
- **On Opus 4.7+ the judge can no longer pin `temperature=0`.** Those models reject sampling params, so the adapter omits `temperature` and the judge relies on the model's *default* sampling — i.e. **more** run-to-run variance, not less. One more reason κ matters: we measure agreement under the sampling the model actually uses, not under an idealized pinned-zero temperature.
- **N = 30 → a wide confidence interval.** The point estimate is indicative, not precise. The CI is *stated*, not computed (bootstrapping 30 points would over-promise).
- **A single person labelled the set.** This is one-rater agreement, not consensus gold; there is no second annotator or adjudication.
- **The κ paradox / base-rate sensitivity:** with skewed marginals (global 13 pass / 17 fail) a high `p_o` can still yield a low or even undefined κ. So the report **always shows `p_o` and the confusion matrix beside κ** — never κ alone. When both raters collapse to one class (`1 − p_e = 0`) κ is mathematically undefined and is reported as `null` / band `undefined`, keeping the real `p_o`, rather than a fabricated 0.0 or 1.0.
- **`parse_failed` verdicts are EXCLUDED from κ and counted separately.** A parse failure is not a judgment, and its neutral 0.5 would otherwise count as a pass at the boundary; it is dropped before binarizing and surfaced as a count per scope.
- **Landis-Koch bands** (slight / fair / moderate / substantial / …) are reported for orientation, but the **band boundaries are arbitrary conventions**, not objective thresholds.
- **`human_label` (categorical) drives κ;** `human_score` (0/1) is a redundant numeric mirror kept only to cross-check the label at load time, never averaged in.
- **`--judge mock` is a wiring smoke test, not a calibration** — it measures the lexical mock against the labels, not the judge being calibrated. The CLI says so on stderr and the report records `judge: "mock"` plainly.

---

---

[← back to the README](../README.md)
