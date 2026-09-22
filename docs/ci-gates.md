# CI regression gates (F7) — the full contract

What each gate counts as a regression, what it guarantees, and — just as important —
what it does **not**. The one-screen summary is on the
[front page](../README.md#ci-regression-gates-f7).

## Eval gate

`aegis eval gate` runs the eval suite on the **deterministic, offline MockJudge/MockProvider** and compares the result to a **committed baseline** (`src/aegis/evals/baselines/golden.json` — versioned, *not* gitignored; it is the gate contract). On a regression it exits non-zero, so a required CI check blocks the PR. The CI job is `eval-gate` in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml): no key, no SDK, no network.

```bash
aegis eval gate                    # CI runs this: mock vs committed baseline; exit 1 on regression
aegis eval gate --update-baseline  # regenerate the contract after an intended change, then commit it
```

A **regression** is any of: a per-level mean drop beyond `--tolerance` (default 0.005); a **per-case score drop** on any applicable level (exact after 6-dp rounding — this catches sub-threshold L2 erosion that does *not* flip pass/fail); a per-case **pass→fail** flip; an L2 case dropping out of the judged set; or a **new `parse_failed`**. Each is printed naming the exact case/level. A stale or mismatched baseline (case-set changed, judge ≠ `mock`) exits **2** ("regenerate"), distinct from a real regression (**1**). Improvements never fail the gate.

**What it guarantees — and what it does not:**

- **It catches regressions; it does NOT validate the real judge.** The gate runs the **mock**, so it guards the eval **pipeline** (scoring, aggregation, dataset, wiring) against the baseline. Whether the *real* judge is any good is a **separate** question answered by [Judge calibration (F5)](evals.md#judge-calibration-f5) (Cohen's κ), which is directional, not ground truth.
- **The guarantee is "no SILENT regression", not "no regression ever".** `--update-baseline` *can* re-baseline worse scores and make the gate green — but the baseline is committed, so re-baselining a regression is a **visible diff in the PR**: a named, blocking, reviewable event. The gate turns a regression into noise that a human reviewer sees; **review is the final backstop**, not the gate alone.
- **A self-consistency test locks the baseline to the code.** A pytest asserts the committed baseline exactly equals a fresh mock run, so a scoring or golden-set change that forgets `--update-baseline` fails locally *before* CI — the committed floor can never silently lag reality.
- **`parse_failed` is a latent, forward-looking tripwire.** The mock never parse-fails, so it cannot fire under today's offline gate; it exists for a future real-judge baseline and is exercised only via the pure comparator's unit tests.
### Red-team gate

`aegis redteam gate` scores the committed attack catalog against the F2 guardrails on the **same hermetic, offline pipeline** as `aegis redteam run` (`build_redteam_settings` pins every field — no key, no SDK, no network) and compares to a committed baseline (`src/aegis/redteam/baselines/redteam.json` — versioned, *not* gitignored). The CI job is `redteam-gate`.

```bash
aegis redteam gate                    # CI runs this: catalog vs committed baseline; exit 1 on regression
aegis redteam gate --update-baseline  # regenerate the contract after an intended change, then commit it
```

- **What's a regression.** An attack the baseline recorded as **caught** (blocked/redacted) that now **passes** (`attack_now_passing`); a **block downgraded to a mere redaction** (`detection_downgraded`); or a per-category detection-rate drop beyond `--tolerance`. A stale/remapped/mismatched baseline (attack-set changed, category remapped, mode ≠ `mock-offline`) exits **2**. A blocked attack whose guardrail **code** changes while still blocked is an **informational note, not a failure** (the codes have no strength ordering, and the short-circuit pipeline can legitimately change which stage fires). **Improvements never fail** — a gap that gets caught, or a redaction promoted to a block, is welcome; you re-baseline to lock it in.
- **You cannot hide a red-team regression by calling it a "known gap".** The baseline records each attack's *prior observed* outcome **independent of the catalog's `expected_outcome`/`is_known_gap`**, so weakening a guardrail and relabeling the now-passing attack a gap **in the same PR still fails** `attack_now_passing` — a catalog edit cannot override the frozen baseline. The detection rate is **coverage-against-catalog (it includes the named gaps), never "security coverage."**
- **Same guarantee as the eval gate: "no SILENT regression", not "no regression".** The only green path past a real weakening is `--update-baseline`, which writes a visible `blocked/redacted → passed` diff into the committed baseline — the single highest-signal line in a red-team PR — that a human must approve. A self-consistency test locks the committed baseline to a fresh hermetic run, so a guardrail/catalog change that forgets `--update-baseline` fails locally before CI. **Review is the final backstop.**

**Enabling the block (one-time, maintainer action in GitHub):** Settings → Branches → branch-protection rule for `main` → *Require status checks to pass before merging* → require the **`eval-gate`** and **`redteam-gate`** checks (alongside `lint-and-test`). The check names must match the job ids **exactly** or GitHub silently never blocks. Until both are required, the jobs run and report but do not hard-block; the repo cannot self-apply branch protection, and a re-baseline PR (`--update-baseline`) needs explicit human sign-off.

---

---

[← back to the README](../README.md)
