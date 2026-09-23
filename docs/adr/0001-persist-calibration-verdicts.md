# ADR 0001 — Persist the judge's per-case verdicts instead of dropping the κ claim

**Status:** accepted · 2026-09-22

## Context

`README.md` announced **Cohen's κ ≈ 0.93** for judge-vs-human agreement. `.gitignore` ignores
`reports/`, which is where `aegis calibrate` writes, so **no artifact backed the number**.

What a reader without an API key actually got:

| command | result |
|---|---|
| `aegis calibrate --judge geval` | exit 2, `ANTHROPIC_API_KEY is not set` |
| `aegis calibrate --judge mock` | `global: kappa=-0.164 ... band=poor` |

A **negative** κ, against a README promising 0.93. That is the single finding most likely to
make a reader distrust every other number in the repo.

The enabling detail: `compute_calibration(cases, verdicts, ...)` is already a **pure function**
over a verdict list. The scoring call is the only step that needs a key and a network.

## Decision

Add `--dump-verdicts` and `--from-verdicts` to `aegis calibrate`. Run the real judge **once**,
commit the 30 per-case verdicts to `artifacts/`, and recompute the published κ from those bytes
offline. Ship the artifact inside the wheel too, so a `pipx install` with no checkout can also
reproduce it.

## Alternative rejected

**Delete the 0.93 from the front page.** Half an hour instead of four, and it resolves the
criticism by subtraction. Rejected because calibrating an LLM judge against hand labels is the
project's actual differentiator — anyone can build a gateway with guardrails; far fewer people
sit down and label 30 cases to measure their own judge. Removing it to dodge a critique would
remove the reason the repo is interesting.

## Consequences

The number became an artifact rather than an assertion, and CI re-derives it on every run, so
the README and the evidence cannot drift apart.

**The cost:** the artifact is frozen to one model and one date. When `claude-opus-4-8` is
retired, the "run it with your own key" path stops reproducing — which is precisely why the
committed file is not a patch but the only durable evidence the number will ever have.
Documented in `artifacts/README.md`.

**An unplanned benefit.** The README used to say the single disagreeing case "is not
recoverable from this run". It is now: `cal-rel-05`, scored **exactly 0.5**, with reasoning that
correctly identifies the false claim. So the lone disagreement is the `>= 0.5` binarization
rounding a deliberately *partial* score toward pass — not a comprehension failure. That is only
visible once per-case verdicts are kept.
