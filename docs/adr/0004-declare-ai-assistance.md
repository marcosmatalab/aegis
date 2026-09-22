# ADR 0004 — Declare the AI assistance instead of rewriting history

**Status:** accepted · 2026-09-22

## Context

Measured with `git log --format=%ad --date=short | sort | uniq -c`:

```
 68  2026-06-22
 44  2026-06-23
 65  2026-06-24
  8  2026-06-25
```

**185 commits in four days**, a 2.6-minute median gap, 27 of them between 00:00 and 03:00,
**zero** `Co-authored-by` trailers, and no mention of AI anywhere in the tree.

Any reader finds that in about thirty seconds. It lands especially badly in a repository whose
entire pitch is radical honesty about its own numbers.

## Decision

State it on the front page, with the exact figure and the command that prints it: what was
designed and decided by the author (the gate contracts, the OWASP mapping, the 30 hand labels,
the honesty statuses, shipping named gaps rather than a rounded rate) and what an assistant
wrote that the author read, tested and owns. The same policy is written down in
`CONTRIBUTING.md`.

## Alternative rejected

**Squash or rebase the history.** Rejected as strictly worse. A history cleaned up after the
fact is detectable, and doing it would directly contradict the value the project sells. The
only coherent move is to say it before anyone has to discover it.

## Consequences

The pace is framed rather than found out, and the honest version is also the better interview
answer.

**The cost:** the history will show a four-day sprint forever. It is not fixable, only
explicable.
