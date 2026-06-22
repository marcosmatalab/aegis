"""L2 TRACE scorer — response quality (relevancy + faithfulness) via the judge.

Runs the judge for relevancy (vs ``reference_answer``) and faithfulness (vs
``context``), using whichever the case provides; L2 is the mean of the available
sub-scores. If the case has neither a reference nor context, L2 is NOT APPLICABLE
(``breakdown["applicable"] == False``) and the runner excludes it from the L2
aggregate (so absence neither inflates nor deflates the suite).

``L2_THRESHOLD`` (0.5) is a per-case DIAGNOSTIC pass mark, deliberately distinct
from the authoritative suite CI gate (later phase; ``.env.example`` uses 0.80).
"""

from __future__ import annotations

from aegis.evals.judge.base import Judge
from aegis.evals.models import EvalCase
from aegis.evals.result import ScoreResult
from aegis.evals.text import flatten

L2_THRESHOLD = 0.5

_RELEVANCY = "relevancy: is the output relevant to and consistent with the reference answer?"
_FAITHFULNESS = "faithfulness: is every claim in the output grounded in the provided context?"


async def score_l2(case: EvalCase, judge: Judge) -> ScoreResult:
    output = flatten(case.actual.final_output)
    subs: list[tuple[str, float]] = []
    breakdown: dict[str, object] = {}

    # Truthy check (not is-not-None) so an empty/blank reference is treated as
    # absent, symmetric with how an empty `context` list is skipped below.
    if case.reference_answer and case.reference_answer.strip():
        verdict = await judge.score(_RELEVANCY, output, reference=case.reference_answer)
        subs.append(("relevancy", verdict.score))
        breakdown["relevancy"] = verdict.score
    if case.context:
        verdict = await judge.score(_FAITHFULNESS, output, context=case.context)
        subs.append(("faithfulness", verdict.score))
        breakdown["faithfulness"] = verdict.score

    if not subs:
        return ScoreResult(
            "L2",
            0.0,
            False,
            ("no reference or context — L2 not applicable",),
            {"applicable": False},
        )

    score = sum(s for _, s in subs) / len(subs)
    passed = score >= L2_THRESHOLD
    breakdown["applicable"] = True
    breakdown["threshold"] = L2_THRESHOLD
    reasons = () if passed else tuple(f"{name}={value:.3f}" for name, value in subs)
    return ScoreResult("L2", score, passed, reasons, breakdown)
