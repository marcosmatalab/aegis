"""Shared trajectory matching primitives.

``match_trajectory`` is the order-insensitive two-pass matcher originally inlined
in the L3 scorer: pass 1 consumes exact (name + args) matches, pass 2 pairs any
remaining same-name calls as wrong-args. Both the L3 scorer and the F4
ToolCorrectness metric build on it, so the matching logic lives in exactly one
place. Args are compared by value (dict equality); ``status`` (a call OUTCOME) is
intentionally NOT part of step identity here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aegis.evals.models import EvalCase, ToolCall
from aegis.evals.text import flatten, phrase_present


@dataclass(frozen=True, slots=True)
class MatchCounts:
    """Outcome of matching an actual trajectory against the expected one."""

    exact: int  # calls matching expected by name AND args
    wrong_args: int  # right tool, wrong args
    missing: int  # expected calls with no actual counterpart
    extra: int  # actual calls beyond what was expected
    len_expected: int
    len_actual: int

    def tool_f1(self) -> float:
        """F1 of exact (name+args) matches. Both sides empty is vacuously 1.0;
        exactly one side empty is 0.0 (all missing or all extra)."""
        if not self.len_expected and not self.len_actual:
            return 1.0
        if not self.len_expected or not self.len_actual:
            return 0.0
        precision = self.exact / self.len_actual
        recall = self.exact / self.len_expected
        return 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0


def match_trajectory(expected: list[ToolCall], actual: list[ToolCall]) -> MatchCounts:
    """Two-pass, order-insensitive match of ``actual`` against ``expected``."""
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
    return MatchCounts(exact, wrong_args, missing, extra, len(expected), len(actual))


# --------------------------------------------------------------------------- #
# F4 trajectory metrics — deterministic, each a MetricScore in 0..1.
#
# These are DIAGNOSTIC sub-metrics (not a level/gate), so they use their own
# MetricScore type rather than ScoreResult (whose `level` is L1/L2/L3).
# --------------------------------------------------------------------------- #


@dataclass(frozen=True, slots=True)
class MetricScore:
    """One trajectory metric for one case. ``applicable=False`` (with score 0.0)
    means the metric has nothing to measure and is excluded from aggregates."""

    name: str
    score: float
    applicable: bool = True
    breakdown: dict[str, Any] = field(default_factory=dict)


def _lcs_len(a: list[Any], b: list[Any]) -> int:
    """Longest common subsequence length over any ``==``-comparable items."""
    if not a or not b:
        return 0
    prev = [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, start=1):
            cur[j] = prev[j - 1] + 1 if x == y else max(prev[j], cur[j - 1])
        prev = cur
    return prev[len(b)]


def _steps(calls: list[ToolCall]) -> list[tuple[str, dict[str, Any]]]:
    """Full step identity = (name, args); ``status`` (an outcome) is excluded."""
    return [(c.name, c.arguments) for c in calls]


def tool_correctness(case: EvalCase) -> MetricScore:
    """F1 over exact (name+args) matches — the order-insensitive correctness of
    the calls (shares L3's matcher). Both trajectories empty is vacuously 1.0."""
    m = match_trajectory(case.expected_trajectory, case.actual.tool_calls)
    return MetricScore(
        "tool_correctness",
        m.tool_f1(),
        True,
        {"exact": m.exact, "wrong_args": m.wrong_args, "missing": m.missing, "extra": m.extra},
    )


def trajectory_accuracy(case: EvalCase) -> MetricScore:
    """Similarity of the whole path to the golden path: LCS over full steps
    (name+args) normalized by the LONGER sequence, so both missing and extra
    steps lower it. Tolerant of insertions/deletions (subsequence), in contrast
    to T-Eval's strict positional match."""
    exp, act = _steps(case.expected_trajectory), _steps(case.actual.tool_calls)
    if not exp and not act:
        score = 1.0
    elif not exp or not act:
        score = 0.0
    else:
        score = _lcs_len(exp, act) / max(len(exp), len(act))
    return MetricScore(
        "trajectory_accuracy",
        score,
        True,
        {"lcs": _lcs_len(exp, act), "len_expected": len(exp), "len_actual": len(act)},
    )


def _milestones(case: EvalCase) -> list[tuple[str, str, str]]:
    """Resolve milestones to (kind, target, description) triples.

    Falls back to one ``tool`` milestone per UNIQUE expected tool name when the
    case declares none, so Progress Rate is measurable over today's golden set
    and richer when an author adds explicit milestones."""
    if case.milestones:
        resolved: list[tuple[str, str, str]] = []
        for m in case.milestones:
            if m.tool:
                resolved.append(("tool", m.tool, m.description))
            else:
                resolved.append(("output", m.output_contains, m.description))
        return resolved
    seen: list[str] = []
    for t in case.expected_trajectory:
        if t.name not in seen:
            seen.append(t.name)
    return [("tool", name, f"call {name}") for name in seen]


def progress_rate(case: EvalCase) -> MetricScore:
    """AgentBoard-style fraction of milestones (subgoals) achieved, ORDER-
    INDEPENDENTLY. Not applicable (excluded) when there are no milestones to
    derive (no explicit milestones and no expected trajectory)."""
    milestones = _milestones(case)
    if not milestones:
        return MetricScore("progress_rate", 0.0, False, {"reason": "no milestones to measure"})

    actual_tools = {c.name for c in case.actual.tool_calls}
    output = flatten(case.actual.final_output)
    detail: list[dict[str, Any]] = []
    achieved = 0
    for kind, target, desc in milestones:
        ok = (target in actual_tools) if kind == "tool" else phrase_present(output, target)
        achieved += ok
        detail.append({"kind": kind, "target": target, "description": desc, "achieved": ok})

    return MetricScore(
        "progress_rate",
        achieved / len(milestones),
        True,
        {"achieved": achieved, "total": len(milestones), "milestones": detail},
    )


def t_eval(case: EvalCase) -> MetricScore:
    """Step-by-step planning accuracy: is the call at each POSITION the expected
    one? Strict positional match (no realignment) normalized by the longer
    sequence, so a single early insertion penalizes every later step."""
    exp, act = _steps(case.expected_trajectory), _steps(case.actual.tool_calls)
    n = max(len(exp), len(act))
    if n == 0:
        return MetricScore(
            "t_eval",
            1.0,
            True,
            {"matched": 0, "len_expected": 0, "len_actual": 0, "first_divergence": None},
        )

    matched = 0
    first_divergence = None
    for i in range(n):
        same = i < len(exp) and i < len(act) and exp[i] == act[i]
        matched += same
        if not same and first_divergence is None:
            first_divergence = i
    return MetricScore(
        "t_eval",
        matched / n,
        True,
        {
            "matched": matched,
            "len_expected": len(exp),
            "len_actual": len(act),
            "first_divergence": first_divergence,
        },
    )


def score_trajectory(case: EvalCase) -> dict[str, MetricScore]:
    """All four F4 trajectory metrics for a case, keyed by metric name."""
    return {
        "tool_correctness": tool_correctness(case),
        "trajectory_accuracy": trajectory_accuracy(case),
        "progress_rate": progress_rate(case),
        "t_eval": t_eval(case),
    }
