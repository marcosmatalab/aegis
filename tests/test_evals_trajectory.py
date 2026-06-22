"""Tests for the shared trajectory matcher (and, later, the F4 metrics)."""

from __future__ import annotations

from aegis.evals.l3_tool import score_l3
from aegis.evals.models import EvalCase, ToolCall
from aegis.evals.trajectory import (
    MatchCounts,
    match_trajectory,
    progress_rate,
    score_trajectory,
    t_eval,
    tool_correctness,
    trajectory_accuracy,
)


def _t(name, **args):
    return ToolCall(name=name, arguments=args)


def _case(expected=None, actual=None, *, final_output="ok", milestones=None):
    return EvalCase.model_validate(
        {
            "id": "c1",
            "user_goal": "g",
            "input_messages": [{"role": "user", "content": "hi"}],
            "expected_trajectory": [{"name": t.name, "arguments": t.arguments} for t in expected]
            if expected
            else [],
            "actual": {
                "final_output": final_output,
                "tool_calls": [{"name": t.name, "arguments": t.arguments} for t in actual]
                if actual
                else [],
            },
            "milestones": milestones or [],
            "expected": {"l1_goal_met": True, "l2_faithful": None, "l3_trajectory_match": True},
        }
    )


# --- match_trajectory ------------------------------------------------------- #
def test_match_exact_in_any_order():
    m = match_trajectory([_t("a", x=1), _t("b")], [_t("b"), _t("a", x=1)])
    assert (m.exact, m.wrong_args, m.missing, m.extra) == (2, 0, 0, 0)


def test_match_wrong_args_counted_once():
    m = match_trajectory([_t("a", x=1)], [_t("a", x=2)])
    assert (m.exact, m.wrong_args, m.missing, m.extra) == (0, 1, 0, 0)


def test_match_missing_and_extra():
    m = match_trajectory([_t("a"), _t("b")], [_t("a"), _t("c")])
    assert m.exact == 1
    assert m.missing == 1  # b
    assert m.extra == 1  # c


def test_match_ignores_status_in_step_identity():
    # status is an outcome, not part of step identity -> still an exact match
    m = match_trajectory([_t("a", x=1)], [ToolCall(name="a", arguments={"x": 1}, status="error")])
    assert m.exact == 1


# --- MatchCounts.tool_f1 ---------------------------------------------------- #
def test_tool_f1_both_empty_is_one():
    assert MatchCounts(0, 0, 0, 0, 0, 0).tool_f1() == 1.0


def test_tool_f1_one_side_empty_is_zero():
    assert MatchCounts(0, 0, 2, 0, 2, 0).tool_f1() == 0.0  # all missing
    assert MatchCounts(0, 0, 0, 2, 0, 2).tool_f1() == 0.0  # all extra


def test_tool_f1_partial():
    # 1 exact of 2 expected, 2 actual -> P=0.5 R=0.5 -> F1=0.5
    assert match_trajectory([_t("a"), _t("b")], [_t("a"), _t("c")]).tool_f1() == 0.5


# --- tool_correctness ------------------------------------------------------- #
def test_tool_correctness_identical_is_one():
    assert tool_correctness(_case([_t("a", x=1)], [_t("a", x=1)])).score == 1.0


def test_tool_correctness_both_empty_is_one():
    assert tool_correctness(_case([], [])).score == 1.0


def test_tool_correctness_wrong_args_is_zero():
    assert tool_correctness(_case([_t("a", x=1)], [_t("a", x=2)])).score == 0.0


def test_tool_correctness_matches_l3_tool_f1():
    # parity with the L3 sub-score it shares the matcher with
    case = _case([_t("a"), _t("b")], [_t("a"), _t("c")])
    assert tool_correctness(case).score == score_l3(case).breakdown["tool_f1"] == 0.5


# --- trajectory_accuracy ---------------------------------------------------- #
def test_trajectory_accuracy_identical_is_one():
    assert trajectory_accuracy(_case([_t("a"), _t("b")], [_t("a"), _t("b")])).score == 1.0


def test_trajectory_accuracy_reorder_is_half():
    # LCS([a,b],[b,a]) = 1, max len 2 -> 0.5
    assert trajectory_accuracy(_case([_t("a"), _t("b")], [_t("b"), _t("a")])).score == 0.5


def test_trajectory_accuracy_insertion_penalized_by_longer_len():
    # LCS([a,b],[x,a,b]) = 2, max len 3 -> 0.667
    s = trajectory_accuracy(_case([_t("a"), _t("b")], [_t("x"), _t("a"), _t("b")])).score
    assert round(s, 3) == 0.667


def test_trajectory_accuracy_uses_subsequence_not_contiguous_substring():
    # interleaved noise: LCS subsequence [a,b,c]=3 over max len 5 -> 0.6.
    # a contiguous-substring (mis)implementation would score 0.2 here, so this
    # is the case that actually distinguishes the documented subsequence semantics.
    case = _case([_t("a"), _t("b"), _t("c")], [_t("a"), _t("x"), _t("b"), _t("y"), _t("c")])
    res = trajectory_accuracy(case)
    assert res.score == 0.6
    assert res.breakdown["lcs"] == 3


def test_trajectory_accuracy_both_empty_is_one():
    assert trajectory_accuracy(_case([], [])).score == 1.0


def test_trajectory_accuracy_one_side_empty_is_zero():
    assert trajectory_accuracy(_case([_t("a")], [])).score == 0.0


# --- progress_rate (order-independent milestones) --------------------------- #
def test_progress_rate_derived_from_expected_all_reached():
    # no explicit milestones -> derived from expected tool names; both present
    case = _case([_t("web_search", q="x"), _t("summarize")], [_t("summarize"), _t("web_search")])
    pr = progress_rate(case)
    assert pr.score == 1.0
    assert pr.breakdown["total"] == 2


def test_progress_rate_partial_explicit_milestones():
    case = _case(actual=[_t("search")], milestones=[{"tool": "search"}, {"tool": "email"}])
    assert progress_rate(case).score == 0.5


def test_progress_rate_output_milestone():
    case = _case(final_output="the answer is 4", milestones=[{"output_contains": "answer"}])
    assert progress_rate(case).score == 1.0


def test_progress_rate_not_applicable_without_milestones():
    pr = progress_rate(_case([], []))
    assert pr.applicable is False
    assert pr.score == 0.0


def test_progress_rate_is_order_independent_unlike_t_eval():
    # reordered trajectory: every milestone still reached (1.0) though order is wrong
    case = _case([_t("a"), _t("b")], [_t("b"), _t("a")])
    assert progress_rate(case).score == 1.0


# --- t_eval (strict positional) --------------------------------------------- #
def test_t_eval_identical_is_one():
    assert t_eval(_case([_t("a"), _t("b")], [_t("a"), _t("b")])).score == 1.0


def test_t_eval_reorder_is_zero_unlike_trajectory_accuracy():
    # swapped pair: no position matches -> 0.0 (vs trajectory_accuracy 0.5)
    case = _case([_t("a"), _t("b")], [_t("b"), _t("a")])
    assert t_eval(case).score == 0.0
    assert trajectory_accuracy(case).score == 0.5


def test_t_eval_early_insertion_tanks_every_later_step():
    # one prefix insertion shifts everything -> 0.0 (vs trajectory_accuracy 0.667)
    case = _case([_t("a"), _t("b")], [_t("x"), _t("a"), _t("b")])
    assert t_eval(case).score == 0.0
    assert round(trajectory_accuracy(case).score, 3) == 0.667


def test_t_eval_prefix_correct_then_diverges():
    # [a,b,c] vs [a,b,x] -> 2/3 match, first divergence at index 2
    case = _case([_t("a"), _t("b"), _t("c")], [_t("a"), _t("b"), _t("x")])
    res = t_eval(case)
    assert round(res.score, 3) == 0.667
    assert res.breakdown["first_divergence"] == 2


def test_t_eval_both_empty_and_single_step():
    assert t_eval(_case([], [])).score == 1.0
    assert t_eval(_case([_t("a")], [_t("a")])).score == 1.0


def test_status_does_not_affect_positional_match():
    # an error-status call identical by name+args still matches positionally
    case = _case([_t("a", x=1)], None)
    case.actual.tool_calls.append(ToolCall(name="a", arguments={"x": 1}, status="error"))
    assert t_eval(case).score == 1.0
    assert tool_correctness(case).score == 1.0


# --- score_trajectory bundle ------------------------------------------------ #
def test_score_trajectory_returns_all_four():
    res = score_trajectory(_case([_t("a")], [_t("a")]))
    assert set(res) == {"tool_correctness", "trajectory_accuracy", "progress_rate", "t_eval"}
    assert all(0.0 <= m.score <= 1.0 for m in res.values())
