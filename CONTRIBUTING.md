# Contributing

This is a portfolio project, so it is not looking for feature contributions — but issues and
corrections are genuinely welcome, especially anything that catches a number in the docs that
does not reproduce.

## How this was built

Aegis was designed and built by **Marcos Mata García** between June and September 2026: most
of it in an intensive sprint of 185 commits between 22 and 25 June, and the release work
(calibration artifact, CI gates, packaging, branch protection) on 22 September, mostly
in a single two-hour session. `git log --format=%ad --date=short | sort | uniq -c` prints exactly that.

**The design is the author's:** the gate contracts and what counts as a regression, the OWASP
category mapping, the 30 hand-labelled calibration cases, the honesty statuses that run through
CLEAR and the evidence builder, and the decision to publish named red-team gaps instead of a
rounded-up rate.

**Every number gets an artifact or a command.** A figure in the docs must be reproducible
offline — see [`artifacts/README.md`](artifacts/README.md) for the pattern. The rule does not
depend on anyone's word.

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
