# Working agreements for this repository

Rules that exist because something went wrong, not because they sound sensible. Each one
names the failure it prevents.

---

## Verification

### Verify by exit code. Never by reading output.

```bash
cmd > /tmp/out.log 2>&1; echo "exit=$?"     # yes
cmd 2>&1 | tail -3                          # NO — tail hides the verdict
```

**Why.** `npm run lint` was reported green after reading `| tail -2`, which showed two blank
lines. Biome had emitted three errors above them and exited 1. CI caught it; the local check
had not. Truncated output is not a signal, and `tail` on a piped command reports *tail's* exit
code, not the command's.

### Do not redirect to `/dev/null` when checking an exit code on Windows.

```bash
cmd > /tmp/out.log 2>&1; echo $?            # yes
cmd > /dev/null 2>&1; echo $?               # NO — can fabricate a failure
```

**Why.** `lint-imports` reports `Contracts: 3 kept, 0 broken` and exits **1** when stdout is
`/dev/null` under Git Bash, and **0** when it is a real file. `rich` (its progress spinner)
misdetects the console, tries to encode an emoji as cp1252 and raises. The contracts were
never broken. Two separate debugging detours were spent on this before the redirection itself
turned out to be the variable. Export `PYTHONIOENCODING=utf-8` as well.

### Run the whole suite, not a filtered subset, before declaring it green.

`pytest tests/test_x.py` skips the guards that only make sense over a full collection — for
instance `test_docs_numbers.py` cannot check the published test count unless it sees every test.

### `.env` breaks the suite locally, and that is expected.

`.env` is gitignored and holds a real `ANTHROPIC_API_KEY`. Five tests assert clean behaviour
*without* a key, and pydantic-settings loads `.env` from the working directory, so they fail
locally and pass in CI. Move it aside for a full run, and restore it with a `trap` so an
interrupt cannot leave it moved:

```bash
restore() { [ -f .env.tmpmove ] && mv .env.tmpmove .env; }
trap restore EXIT INT TERM
mv .env .env.tmpmove
pytest -q
restore; trap - EXIT INT TERM
```

---

## Numbers in documentation

### No figure is hand-written into a README if a command prints it.

Every published number must be recomputable from a committed artifact, and
`tests/test_docs_numbers.py` asserts the README text against that artifact in **both
languages**. Adding tests therefore requires updating the count in the README — that tax is
the point.

**Why.** The READMEs claimed 944 tests for several commits after the suite reached 952. An
external reviewer found it before CI did, because nothing was checking.

### A containment check is not an equality check.

`assert "0.933" in readme` passes while a *second* mention of κ drifts to something else. Collect
**all** occurrences and compare the set. This was found by deliberately mutating one of three
mentions and watching the test stay green.

---

## Changing CI

### Renaming a job is a breaking change to branch protection.

Required status checks match by **exact context name**. A context that never reports stays
pending forever, and the PR is unmergeable with no failing check to point at. Adding a matrix
**is** a rename: `lint-and-test` became `lint-and-test (3.12)` and `lint-and-test (3.13)`.

Rename the job and update the required-context list **in the same change**.

### Check for rulesets, not just branch protection.

`gh api repos/OWNER/REPO/branches/main/protection` does **not** show rulesets. A repository can
enforce both at once, and a correct-looking protection API response can sit alongside a ruleset
blocking every merge:

```bash
gh api repos/OWNER/REPO/rules/branches/main    # the other mechanism
```

Full write-up in [`docs/ci-gates.md`](docs/ci-gates.md).

---

## Honesty rules this project lives by

These are not style preferences; the project's whole claim rests on them.

- **Every number gets an artifact or a command.** If it cannot be reproduced offline, it does
  not go on the front page.
- **A detection rate is allowed to go down.** Disclosing a new red-team gap lowers the headline
  figure. That is correct. A rate that only ever improves is a managed number, not a measured
  one.
- **Re-baselining is a reviewed act.** `--update-baseline` is the one green path past a genuine
  regression, so the diff must be visible and explained in the PR.
- **Declare the assistance.** The history shows a 185-commit sprint and a 2-hour session. Both
  are stated in `CONTRIBUTING.md`, which the README links to. Do not rewrite history to smooth it; a cleaned-up log is both
  detectable and a contradiction of what the project sells.
