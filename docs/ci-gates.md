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

**The block is enabled.** `main` carries a branch-protection rule requiring all six checks —
`lint-and-test (3.12)`, `lint-and-test (3.13)`, `eval-gate`, `redteam-gate`,
`calibration-artifact` and `dashboard` — to pass before a merge, with `strict: true` so a PR
must also be up to date with `main`. A red gate therefore blocks the merge, it does not merely
report.

This is the one claim in the repo that **cannot** be verified from the source tree, because
branch protection lives in GitHub's settings rather than in a file. So the live configuration is
exported and committed as [`branch-protection.json`](branch-protection.json), and anyone with
read access can confirm it themselves:

```bash
gh api repos/marcosmatalab/aegis/branches/main/protection   | jq '.required_status_checks.contexts'
```

Two honest caveats. `enforce_admins` is **false**, so the repository owner can still merge past
a red check — this is a solo project and a hard self-lock would be theatre; the gate's real job
is to make a regression impossible to merge *without noticing*. And a re-baseline PR
(`--update-baseline`) still needs explicit human sign-off, because re-baselining is exactly the
green path past a genuine weakening.

---

## The gate actually blocked two merges, and neither was a demo

A sabotage test is a useful check but a weak proof: it is a failure the author chose, at a
moment the author chose. What follows is better evidence, because nobody wanted either of these
and both cost real time.

Both are the same underlying mistake — **a required-check list and the workflow that produces
it drifting apart** — and they drifted in opposite directions, which is what makes the pair
worth recording.

### Direction 1 — protection written for the final state, applied to an earlier branch

Branch protection on `main` requires six contexts:

```
lint-and-test (3.12)   lint-and-test (3.13)   eval-gate
redteam-gate           calibration-artifact   dashboard
```

Three of those did not exist when the work started. The Python matrix split `lint-and-test`
into two contexts, and `calibration-artifact` was added at the same time. A branch from before
that change therefore emits only **four** of the six.

The effect on PR #28 (the first branch of the series): **eight check runs, all green, merge
blocked** — because two required contexts were not merely failing, they were never reported at
all, and a context that never reports stays pending forever.

That is the gate behaving exactly as designed. "Required" means *required*, not "required if it
happens to run", and a check that silently disappears is precisely the failure mode branch
protection exists to catch.

### Direction 2 — a ruleset left on the old state, applied to the final branch

The more instructive one, because it was an accident rather than a consequence.

A repository **ruleset** named `main-protection` predated this work and also targeted `main`.
Rulesets do not appear in the branch-protection API, so `gh api .../branches/main/protection`
showed a clean, correct configuration while a second mechanism was quietly enforcing a
different one. It required:

```
eval-gate      lint-and-test      redteam-gate
```

That middle context is the **pre-matrix job name**. After the matrix split, `lint-and-test`
could never report again under that exact name. So PR #40 — carrying the finished work, with
all six required contexts passing, three times over — was **permanently unmergeable**, and the
branch-protection API gave no hint why.

Diagnosis took a detour through the wrong hypotheses first (stale `mergeStateStatus`, the
`strict` up-to-date rule, an attribution flag) before `gh api repos/.../rules/branches/main`
showed the second mechanism.

### What was changed, and why

The ruleset was **deleted** rather than corrected. Two enforcement mechanisms maintained in
parallel over one branch is the actual defect; fixing the contexts inside the ruleset would
have left the trap armed for the next rename. Classic branch protection covers the same ground
and is the one with committed evidence in [`branch-protection.json`](branch-protection.json).

### The transferable lesson

Renaming a CI job **is a breaking change to branch protection**, and nothing warns you. A job
rename and the required-context list have to move together, in the same change, or every
subsequent PR blocks on a check that no longer exists. Adding a matrix is a rename:
`lint-and-test` became `lint-and-test (3.12)`.


---

---

[← back to the README](../README.md)
