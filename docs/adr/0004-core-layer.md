# ADR 0004 — Introduce `aegis.core` to break the gateway ↔ guardrails cycle

**Status:** accepted · 2026-09-22

## Context

`aegis.guardrails` imported `ChatCompletionRequest` and `Settings` from `aegis.gateway`, while
`aegis.gateway.proxy` imports `aegis.guardrails`. A genuine import cycle between the HTTP layer
and the layer that is supposed to sit underneath it.

Nothing would have caught it. There was no architecture test, no import linter, and the cycle
did not break anything at runtime, so a 900-test suite stayed green over it.

## Decision

Move `schemas.py` and `config.py` down into a new `aegis.core`, which imports no other Aegis
package, and pin the resulting layering with `.importlinter` as a blocking CI job.

## Alternative rejected

**Leave compatibility shims at the old paths** so the ~44 importing files need not change.
Rejected: the package is pre-1.0 with no external users, and a permanent shim is a permanent
invitation to re-create the cycle through the old name.

## Consequences

Three contracts now hold in CI. Reintroducing the original import fails with the offending edge
named:

```
aegis.guardrails is not allowed to import aegis.gateway:
- aegis.guardrails.pipeline -> aegis.gateway.upstream (l.15)
```

**One correction worth recording:** the obvious layer order is wrong. `evals` must sit **above**
`redteam`, not below, because `evals.persistence` imports the red-team report type. The reverse
order — which looks more natural, red-team being "later" — makes that a forbidden upward import
and the contract fails. The graph decides the order, not the phase numbering.
