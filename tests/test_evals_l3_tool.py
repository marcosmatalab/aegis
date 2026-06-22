"""Tests for the deterministic L3 tool-trajectory scorer."""

from __future__ import annotations

from aegis.evals.l3_tool import score_l3
from aegis.evals.models import EvalCase


def _case(expected_trajectory, actual_tool_calls):
    return EvalCase.model_validate(
        {
            "id": "c1",
            "user_goal": "g",
            "input_messages": [{"role": "user", "content": "hi"}],
            "expected_trajectory": expected_trajectory,
            "actual": {"final_output": "ok", "tool_calls": actual_tool_calls},
            "expected": {"l1_goal_met": True, "l2_faithful": None, "l3_trajectory_match": True},
        }
    )


def _t(name, **args):
    return {"name": name, "arguments": args}


def test_exact_match_in_order_passes():
    res = score_l3(_case([_t("a", x=1), _t("b", y=2)], [_t("a", x=1), _t("b", y=2)]))
    assert res.passed is True
    assert res.score == 1.0


def test_both_empty_passes():
    res = score_l3(_case([], []))
    assert res.passed is True
    assert res.score == 1.0


def test_args_compared_by_value_not_key_order():
    res = score_l3(_case([_t("a", x=1, y=2)], [{"name": "a", "arguments": {"y": 2, "x": 1}}]))
    assert res.passed is True


def test_wrong_args_fails():
    res = score_l3(_case([_t("a", x=1)], [_t("a", x=999)]))
    assert res.passed is False
    assert res.breakdown["wrong_args"] == 1
    assert res.breakdown["exact"] == 0


def test_missing_tool_fails():
    res = score_l3(_case([_t("a"), _t("b")], [_t("a")]))
    assert res.passed is False
    assert res.breakdown["missing"] == 1


def test_extra_tool_fails():
    res = score_l3(_case([_t("a")], [_t("a"), _t("b")]))
    assert res.passed is False
    assert res.breakdown["extra"] == 1


def test_expected_empty_but_actual_present_fails():
    res = score_l3(_case([], [_t("a")]))
    assert res.passed is False
    assert res.score == 0.0


def test_misordered_distinct_tools_fails_on_order():
    # same tools, swapped order -> exact F1 == 1.0 but order < 1.0
    res = score_l3(_case([_t("a"), _t("b")], [_t("b"), _t("a")]))
    assert res.passed is False
    assert res.breakdown["tool_f1"] == 1.0
    assert res.breakdown["order"] < 1.0
    assert res.score < 1.0


def test_duplicate_same_name_permuted_args_passes():
    # the two-pass match makes identical-name calls order-insensitive for correctness
    res = score_l3(_case([_t("t", a=1), _t("t", a=2)], [_t("t", a=2), _t("t", a=1)]))
    assert res.passed is True
    assert res.breakdown["exact"] == 2
    assert res.breakdown["order"] == 1.0


def test_all_tools_missing_when_expected():
    res = score_l3(_case([_t("a"), _t("b")], []))
    assert res.passed is False
    assert res.breakdown["missing"] == 2
    assert res.breakdown["tool_f1"] == 0.0
    assert res.breakdown["order"] == 0.0


def test_nested_and_list_args_compared_by_value():
    res = score_l3(
        _case(
            [{"name": "f", "arguments": {"a": {"x": [1, 2]}, "b": [3]}}],
            [{"name": "f", "arguments": {"b": [3], "a": {"x": [1, 2]}}}],
        )
    )
    assert res.passed is True
