"""Tests for the deterministic L1 session scorer and text matching."""

from __future__ import annotations

from aegis.evals.l1_session import score_l1
from aegis.evals.models import EvalCase
from aegis.evals.text import phrase_present


def _case(**actual_and_criteria):
    body = {
        "id": "c1",
        "user_goal": "g",
        "input_messages": [{"role": "user", "content": "hi"}],
        "expected_trajectory": actual_and_criteria.get("expected_trajectory", []),
        "success_criteria": actual_and_criteria.get("success_criteria", {}),
        "actual": actual_and_criteria.get("actual", {"final_output": "ok", "tool_calls": []}),
        "expected": {"l1_goal_met": True, "l2_faithful": None, "l3_trajectory_match": True},
    }
    return EvalCase.model_validate(body)


# --- phrase_present (whole-word matching) ----------------------------------- #
def test_phrase_present_whole_word():
    assert phrase_present("It is 30°C and sunny", "30") is True
    assert phrase_present("It is 30°C", "New York") is False
    assert phrase_present("a catastrophe happened", "cat") is False  # not a substring match
    assert phrase_present("the total is 1024", "24") is False
    assert phrase_present("welcome to New York city", "new york") is True


# --- L1 scoring ------------------------------------------------------------- #
def test_goal_met_all_checks_pass():
    case = _case(
        success_criteria={"must_include": ["Madrid", "30"], "must_not_include": ["error"]},
        actual={"final_output": "It is 30°C in Madrid.", "tool_calls": []},
    )
    res = score_l1(case)
    assert res.passed is True
    assert res.score == 1.0


def test_missing_keyword_fails():
    case = _case(
        success_criteria={"must_include": ["Madrid", "humidity"]},
        actual={"final_output": "It is sunny in Madrid.", "tool_calls": []},
    )
    res = score_l1(case)
    assert res.passed is False
    assert res.score == 0.5


def test_forbidden_keyword_fails():
    case = _case(
        success_criteria={"must_include": ["Madrid"], "must_not_include": ["error"]},
        actual={"final_output": "error: could not reach Madrid service", "tool_calls": []},
    )
    assert score_l1(case).passed is False


def test_required_tool_not_called_fails():
    case = _case(
        expected_trajectory=[{"name": "get_weather", "arguments": {}}],
        success_criteria={"must_include": ["Madrid"]},
        actual={"final_output": "Madrid is nice", "tool_calls": []},
    )
    res = score_l1(case)
    assert res.passed is False
    assert "failed tool_called:get_weather" in res.reasons


def test_required_tool_called_passes():
    case = _case(
        expected_trajectory=[{"name": "get_weather", "arguments": {}}],
        success_criteria={"must_include": ["Madrid"]},
        actual={"final_output": "Madrid", "tool_calls": [{"name": "get_weather", "arguments": {}}]},
    )
    assert score_l1(case).passed is True


def test_fail_closed_when_no_criteria_and_no_tools():
    case = _case(actual={"final_output": "anything", "tool_calls": []})
    res = score_l1(case)
    assert res.passed is False
    assert res.score == 0.0


def test_whitespace_only_output_fails_keyword():
    case = _case(
        success_criteria={"must_include": ["Madrid"]},
        actual={"final_output": "   ", "tool_calls": []},
    )
    assert score_l1(case).passed is False


def test_none_output_fails_keyword():
    case = _case(
        success_criteria={"must_include": ["Madrid"]},
        actual={"final_output": None, "tool_calls": []},
    )
    assert score_l1(case).passed is False
