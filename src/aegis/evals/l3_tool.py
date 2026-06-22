"""L3 TOOL scorer — deterministic tool-call correctness (no LLM).

Combines two sub-scores:
  * ToolCorrectness (F1) over EXACT (name + args) matches, computed with a
    two-pass match (pass 1 consumes exact name+args matches; pass 2 pairs any
    remaining same-name calls as wrong-args) so duplicate/permuted-arg calls are
    scored order-insensitively and fairly;
  * OrderAccuracy via the longest common subsequence of the tool-name sequences.

``score`` is their mean; ``passed`` requires an exact trajectory match (no
missing/extra/wrong-args calls and correct order). Args are compared by value
(dict equality), so key order does not matter.

Known limitation: OrderAccuracy is computed over tool NAMES, so two calls to the
SAME tool are order-insensitive for correctness (duplicate calls with permuted
args still pass). Argument-order across same-named calls is intentionally not
distinguished here; finer per-position arg-order sensitivity is a later
trajectory-metrics concern (T-Eval), out of F3 scope.
"""

from __future__ import annotations

from aegis.evals.models import EvalCase, ToolCall
from aegis.evals.result import ScoreResult
from aegis.evals.trajectory import match_trajectory


def _lcs_len(a: list[str], b: list[str]) -> int:
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, start=1):
            cur[j] = prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1])
        prev = cur
    return prev[len(b)]


def score_l3(case: EvalCase) -> ScoreResult:
    expected: list[ToolCall] = case.expected_trajectory
    actual: list[ToolCall] = case.actual.tool_calls

    if not expected and not actual:
        return ScoreResult(
            "L3", 1.0, True, (), {"exact": 0, "wrong_args": 0, "missing": 0, "extra": 0}
        )

    m = match_trajectory(expected, actual)
    tool_f1 = m.tool_f1()  # one side empty (other not) -> 0.0; both-empty handled above

    # an empty expected means actual has spurious calls, so order is 0.0 (nothing
    # expected was produced in order).
    order = (
        0.0
        if not expected
        else _lcs_len([t.name for t in expected], [t.name for t in actual]) / len(expected)
    )

    score = (tool_f1 + order) / 2
    passed = m.missing == 0 and m.extra == 0 and m.wrong_args == 0 and order == 1.0

    reasons: list[str] = []
    if m.missing:
        reasons.append(f"{m.missing} expected tool call(s) missing")
    if m.extra:
        reasons.append(f"{m.extra} unexpected tool call(s)")
    if m.wrong_args:
        reasons.append(f"{m.wrong_args} tool call(s) with wrong arguments")
    if order < 1.0 and not reasons:
        reasons.append("tool calls out of order")

    return ScoreResult(
        "L3",
        score,
        passed,
        tuple(reasons),
        {
            "exact": m.exact,
            "wrong_args": m.wrong_args,
            "missing": m.missing,
            "extra": m.extra,
            "tool_f1": tool_f1,
            "order": order,
        },
    )
