# Contributing

This is a portfolio project, so it is not looking for feature contributions — but issues and
corrections are genuinely welcome, especially anything that catches a number in the docs that
does not reproduce.

## AI assistance policy

This repository was built with **heavy AI coding-assistant use**, and says so on the front
page rather than leaving it to be discovered from `git log`. The rules it was built under, and
the rules for any future change:

1. **Declare it, never disguise it.** 185 of the commits landed between 22 and 25 June 2026.
   That pace is stated in the README's [Provenance](README.md#provenance-how-this-was-built)
   section. The history is not rewritten, squashed or back-dated to look more organic.
2. **Design decisions are the author's.** The gate contracts and what counts as a regression,
   the OWASP category mapping, the 30 hand-labelled calibration cases, the honesty statuses,
   and the decision to publish named red-team gaps instead of a rounded-up rate.
3. **Generated code is read, tested and owned.** "An assistant wrote it" is not a defence for
   anything in here. If it ships, the author can explain it.
4. **Every number gets an artifact or a command.** This is the rule that actually settles the
   question, because it does not depend on anyone's word. A figure in the docs must be
   reproducible offline — see [`artifacts/README.md`](artifacts/README.md) for the pattern.

## Working on it

```bash
python3.12 -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Before opening a PR, run what CI runs:

```bash
ruff check . && ruff format --check .
pytest -q
aegis eval gate                       # eval regression vs the committed baseline
aegis redteam gate                    # red-team regression vs the committed baseline
cd dashboard && npm ci && npm run lint && npm run typecheck && npm test && npm run build
```

All of it is offline and keyless. If you need a key to make a check pass, something is wrong.

## Changing a baseline

`src/aegis/evals/baselines/golden.json` and `src/aegis/redteam/baselines/redteam.json` are
**contracts**, not caches. A diff in either is the highest-signal line in the whole PR: it says
detection or scoring changed. Never re-baseline to make a red gate go green without saying, in
the PR description, what changed and why the new numbers are correct.

## Changing the calibration set

`src/aegis/evals/datasets/calibration.jsonl` is hashed into
`artifacts/calibration-geval-2026-09-22.jsonl`, so editing it will fail
`tests/test_evals_calibration_artifact.py` on purpose. That test is the tripwire that stops the
README's κ and its evidence from drifting apart. If you really are re-labelling, regenerate the
artifact with a real judge run and update the README's figures in the same PR.

## Reporting a vulnerability

See [`SECURITY.md`](SECURITY.md).
