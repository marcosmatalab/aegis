"""Deterministic, keyless MockJudge for offline L2 tests.

Two transparent heuristics so tests can assert exact numbers:
  * relevancy = token-overlap F1 between output and reference;
  * faithfulness = fraction of the output's content tokens that also appear in
    the context.

IMPORTANT: both heuristics are purely LEXICAL — relevancy rewards token overlap
and faithfulness rewards token containment, neither understands meaning. A
reordered copy of the context scores faithfulness 1.0, and the mock can only
reward outputs that lexically overlap the reference/context (verbatim, permuted,
or subset) — it CANNOT reward a genuine paraphrase. So every "pass" the
MockJudge produces is a lexical match, by construction. This is an intentional,
documented limitation of the deterministic mock (and a known weakness of cheap
judges); the real value is that the eval GATE catches regressions, not that the
judge is ground truth. The real (G-Eval) judge is a separate, clearly-stubbed
backend.
"""

from __future__ import annotations

from aegis.evals.judge.base import Judge, JudgeVerdict
from aegis.evals.text import content_tokens


def _f1(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if inter == 0:
        return 0.0
    precision = inter / len(a)
    recall = inter / len(b)
    return 2 * precision * recall / (precision + recall)


class MockJudge(Judge):
    name = "mock"

    async def score(
        self,
        criteria: str,
        output: str,
        *,
        reference: str | None = None,
        context: list[str] | None = None,
    ) -> JudgeVerdict:
        out = content_tokens(output or "")
        if "faith" in criteria.lower():
            ctx = content_tokens(" ".join(context or []))
            if not out or not ctx:
                return JudgeVerdict(
                    0.0, "no output content or no context to ground against", criteria, self.name
                )
            grounded = len(out & ctx)
            score = grounded / len(out)
            reason = (
                f"{grounded}/{len(out)} output content tokens grounded in context "
                "(lexical containment, not entailment)"
            )
            return JudgeVerdict(score, reason, criteria, self.name)

        ref = content_tokens(reference or "")
        score = _f1(out, ref)
        return JudgeVerdict(
            score, f"token-overlap F1 with reference = {score:.3f}", criteria, self.name
        )
