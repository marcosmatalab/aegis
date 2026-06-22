"""Tests for the Agent-as-a-Judge trajectory judge (deterministic mock)."""

from __future__ import annotations

import asyncio

import pytest

from aegis.evals.judge.agent import (
    AgentJudge,
    MockTrajectoryJudge,
    build_trajectory_judge,
    build_trajectory_prompt,
)
from aegis.evals.judge.geval import JudgeNotConfiguredError
from aegis.evals.models import EvalCase
from aegis.gateway.config import Settings


def _case(calls):
    return EvalCase.model_validate(
        {
            "id": "c1",
            "user_goal": "g",
            "input_messages": [{"role": "user", "content": "hi"}],
            "expected_trajectory": [],
            "actual": {"final_output": "ok", "tool_calls": calls},
            "expected": {"l1_goal_met": True, "l2_faithful": None, "l3_trajectory_match": True},
        }
    )


def _assess(case, judge=None):
    return asyncio.run((judge or MockTrajectoryJudge()).assess(case))


def _call(name, status="ok", **args):
    return {"name": name, "arguments": args, "status": status}


# --- clean / trivial -------------------------------------------------------- #
def test_clean_trajectory_scores_one():
    v = _assess(_case([_call("a"), _call("b")]))
    assert v.score == 1.0
    assert v.has_loop is False
    assert v.redundant_steps == 0
    assert v.recovered_from_error is None


def test_empty_trajectory_is_trivially_clean():
    v = _assess(_case([]))
    assert v.score == 1.0
    assert "no tool calls" in v.reasoning


def test_single_step_is_clean():
    assert _assess(_case([_call("only")])).score == 1.0


# --- loops ------------------------------------------------------------------ #
def test_consecutive_repeat_is_a_loop():
    v = _assess(_case([_call("a"), _call("a")]))
    assert v.has_loop is True
    # loop (-0.5) and the repeat is also redundant (-0.2) -> 0.3
    assert round(v.score, 3) == 0.3


def test_cycle_is_a_loop():
    v = _assess(_case([_call("a"), _call("b"), _call("a"), _call("b")]))
    assert v.has_loop is True


# --- redundancy (isolated from loops) --------------------------------------- #
def test_non_adjacent_repeat_is_redundant_not_a_loop():
    v = _assess(_case([_call("a"), _call("b"), _call("a")]))
    assert v.has_loop is False
    assert v.redundant_steps == 1
    assert round(v.score, 3) == 0.8  # -0.2


def test_redundant_penalty_is_capped():
    # five identical-by-(name,args) repeats would be -1.0 uncapped; cap is -0.6.
    # (consecutive repeats also trip the loop flag, so this is the floor case)
    calls = [_call("x", k=1) for _ in range(6)]
    v = _assess(_case(calls))
    assert v.redundant_steps == 5
    assert v.score == 0.0  # loop(-0.5) + redundant cap(-0.6) -> clamped at 0


# --- error recovery (status field) ------------------------------------------ #
def test_recovered_error_small_penalty():
    # error then a successful retry on the SAME tool with corrected args
    v = _assess(_case([_call("geo", status="error", city="Madird"), _call("geo", city="Madrid")]))
    assert v.recovered_from_error is True
    assert round(v.score, 3) == 0.9  # -0.1, no redundancy (args differ)


def test_unrecovered_error_larger_penalty():
    v = _assess(_case([_call("search", status="error")]))
    assert v.recovered_from_error is False
    assert round(v.score, 3) == 0.7  # -0.3


def test_error_then_ok_on_different_tool_is_not_recovery():
    # recovery requires a later OK on the SAME tool; a later OK on a different
    # tool must NOT count (pins the name-equality check in _error_recovery)
    v = _assess(_case([_call("fetch", status="error"), _call("notify")]))
    assert v.recovered_from_error is False
    assert round(v.score, 3) == 0.7  # unrecovered penalty, not the recovered one


def test_no_error_signal_means_recovery_none():
    assert _assess(_case([_call("a")])).recovered_from_error is None


# --- determinism ------------------------------------------------------------ #
def test_deterministic():
    case = _case([_call("a"), _call("b"), _call("a")])
    assert _assess(case) == _assess(case)


# --- real backend stub + factory + prompt ----------------------------------- #
def test_agent_backend_is_a_clear_stub():
    judge = AgentJudge(Settings(agent_judge_backend="agent"))
    with pytest.raises(JudgeNotConfiguredError):
        asyncio.run(judge.assess(_case([_call("a")])))


def test_factory_selects_backend():
    assert isinstance(build_trajectory_judge(Settings()), MockTrajectoryJudge)
    assert isinstance(build_trajectory_judge(Settings(agent_judge_backend="agent")), AgentJudge)


def test_prompt_renders_trajectory():
    p = build_trajectory_prompt(_case([_call("a", x=1), _call("b", status="error")]))
    assert "a({'x': 1}) -> ok" in p
    assert "-> error" in p
    assert build_trajectory_prompt(_case([])).find("(no tool calls)") != -1
