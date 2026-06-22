"""Tests for the shared trajectory matcher (and, later, the F4 metrics)."""

from __future__ import annotations

from aegis.evals.models import ToolCall
from aegis.evals.trajectory import MatchCounts, match_trajectory


def _t(name, **args):
    return ToolCall(name=name, arguments=args)


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
