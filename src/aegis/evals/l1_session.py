"""L1 SESSION scorer — deterministic task-completion / goal accuracy (no LLM).

A case passes L1 iff every required tool was called AND every ``must_include``
keyword is present (as a whole word) AND no ``must_not_include`` keyword is
present. ``score`` is the fraction of sub-checks satisfied; ``passed`` is the
strict AND. With neither success criteria nor expected tools, L1 fails closed
(0.0) rather than vacuously passing.
"""

from __future__ import annotations

from aegis.evals.models import EvalCase
from aegis.evals.result import ScoreResult
from aegis.evals.text import flatten, phrase_present


def score_l1(case: EvalCase) -> ScoreResult:
    sc = case.success_criteria
    output = flatten(case.actual.final_output)
    expected_tools = sorted({t.name for t in case.expected_trajectory})
    actual_tools = {t.name for t in case.actual.tool_calls}

    checks: list[tuple[str, bool]] = []
    for tool in expected_tools:
        checks.append((f"tool_called:{tool}", tool in actual_tools))
    for keyword in sc.must_include:
        checks.append((f"include:{keyword}", phrase_present(output, keyword)))
    for keyword in sc.must_not_include:
        checks.append((f"exclude:{keyword}", not phrase_present(output, keyword)))

    if not checks:
        return ScoreResult(
            "L1",
            0.0,
            False,
            ("no success criteria or expected tools defined (fail-closed)",),
            {"checks": {}},
        )

    passed_count = sum(1 for _, ok in checks if ok)
    score = passed_count / len(checks)
    reasons = tuple(f"failed {name}" for name, ok in checks if not ok)
    return ScoreResult("L1", score, passed_count == len(checks), reasons, {"checks": dict(checks)})
