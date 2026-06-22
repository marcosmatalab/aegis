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
"""

from __future__ import annotations

from aegis.evals.models import EvalCase, ToolCall
from aegis.evals.result import ScoreResult


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

    exp_matched = [False] * len(expected)
    act_used = [False] * len(actual)

    # pass 1: exact (name + args) matches
    for i, e in enumerate(expected):
        for j, a in enumerate(actual):
            if not act_used[j] and a.name == e.name and a.arguments == e.arguments:
                exp_matched[i] = True
                act_used[j] = True
                break

    # pass 2: remaining same-name calls -> wrong args
    wrong_args = 0
    for i, e in enumerate(expected):
        if exp_matched[i]:
            continue
        for j, a in enumerate(actual):
            if not act_used[j] and a.name == e.name:
                act_used[j] = True
                wrong_args += 1
                break

    exact = sum(exp_matched)
    missing = len(expected) - exact - wrong_args
    extra = len(actual) - exact - wrong_args

    if not expected or not actual:
        tool_f1 = 0.0  # one side empty, the other not -> all extra or all missing
    else:
        precision = exact / len(actual)
        recall = exact / len(expected)
        tool_f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

    # both-empty already returned 1.0 above; here an empty expected means actual
    # has spurious calls, so order is 0.0 (nothing expected was produced in order).
    order = (
        0.0
        if not expected
        else _lcs_len([t.name for t in expected], [t.name for t in actual]) / len(expected)
    )

    score = (tool_f1 + order) / 2
    passed = missing == 0 and extra == 0 and wrong_args == 0 and order == 1.0

    reasons: list[str] = []
    if missing:
        reasons.append(f"{missing} expected tool call(s) missing")
    if extra:
        reasons.append(f"{extra} unexpected tool call(s)")
    if wrong_args:
        reasons.append(f"{wrong_args} tool call(s) with wrong arguments")
    if order < 1.0 and not reasons:
        reasons.append("tool calls out of order")

    return ScoreResult(
        "L3",
        score,
        passed,
        tuple(reasons),
        {
            "exact": exact,
            "wrong_args": wrong_args,
            "missing": missing,
            "extra": extra,
            "tool_f1": tool_f1,
            "order": order,
        },
    )
