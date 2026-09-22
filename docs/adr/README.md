# Architecture decision records

One file per decision that would otherwise have to be re-argued from scratch. Each records
what was decided, the **measurements** that forced it, the alternative that was rejected and
why, and the cost being accepted.

The format is deliberately blunt about trade-offs: a decision record that only lists upsides
is marketing, not a record.

| ADR | Decision |
|---|---|
| [0001](0001-persist-calibration-verdicts.md) | Persist the judge's per-case verdicts instead of dropping the κ claim |
| [0002](0002-install-from-git-tags.md) | Distribute from git tags, not PyPI |
| [0003](0003-dashboard-static-export.md) | Ship the dashboard as a static export on GitHub Pages |
| [0004](0004-core-layer.md) | Introduce `aegis.core` to break the gateway ↔ guardrails cycle |
| [0005](0005-disclose-more-gaps.md) | Let the red-team detection rate fall when coverage improves |
