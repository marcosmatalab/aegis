"""Tests for the eval-case pydantic models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from aegis.evals.models import CaseTrace, EvalCase, Milestone, ToolCall


def _case(**overrides):
    body = {
        "id": "c1",
        "user_goal": "do the thing",
        "input_messages": [{"role": "user", "content": "hi"}],
        "expected_trajectory": [],
        "reference_answer": None,
        "context": [],
        "success_criteria": {"must_include": [], "must_not_include": []},
        "actual": {"final_output": "hello", "tool_calls": []},
        "expected": {"l1_goal_met": True, "l2_faithful": None, "l3_trajectory_match": True},
    }
    body.update(overrides)
    return body


def test_minimal_case_parses():
    case = EvalCase.model_validate(_case())
    assert case.id == "c1"
    assert case.actual.final_output == "hello"
    assert case.expected.l2_faithful is None


def test_empty_input_messages_rejected():
    with pytest.raises(ValidationError):
        EvalCase.model_validate(_case(input_messages=[]))


@pytest.mark.parametrize("bad_id", ["Has Space", "UPPER", "weird_underscore", ""])
def test_bad_id_rejected(bad_id):
    with pytest.raises(ValidationError):
        EvalCase.model_validate(_case(id=bad_id))


def test_unknown_field_rejected():
    # extra='forbid' catches typos in hand-authored golden lines
    with pytest.raises(ValidationError):
        EvalCase.model_validate(_case(expectd={"l1_goal_met": True}))


def test_tool_call_empty_name_rejected():
    with pytest.raises(ValidationError):
        ToolCall(name="", arguments={})


def test_l2_faithful_without_reference_or_context_rejected():
    with pytest.raises(ValidationError):
        EvalCase.model_validate(
            _case(
                reference_answer=None,
                context=[],
                expected={"l1_goal_met": True, "l2_faithful": True, "l3_trajectory_match": True},
            )
        )


def test_l2_faithful_with_reference_ok():
    case = EvalCase.model_validate(
        _case(
            reference_answer="the answer",
            expected={"l1_goal_met": True, "l2_faithful": True, "l3_trajectory_match": True},
        )
    )
    assert case.expected.l2_faithful is True


def test_tool_calls_parse_into_models():
    case = EvalCase.model_validate(
        _case(
            expected_trajectory=[{"name": "search", "arguments": {"q": "x"}}],
            actual={
                "final_output": "ok",
                "tool_calls": [{"name": "search", "arguments": {"q": "x"}}],
            },
        )
    )
    assert case.expected_trajectory[0] == ToolCall(name="search", arguments={"q": "x"})


# --- F4 schema additions ---------------------------------------------------- #
def test_tool_call_status_defaults_ok_and_parses_error():
    assert ToolCall(name="x").status == "ok"
    assert ToolCall(name="x", status="error").status == "error"


def test_tool_call_invalid_status_rejected():
    with pytest.raises(ValidationError):
        ToolCall(name="x", status="weird")


def test_case_defaults_have_no_trace_and_no_milestones():
    case = EvalCase.model_validate(_case())
    assert case.trace is None
    assert case.milestones == []


def test_trace_parses_and_rejects_negatives():
    case = EvalCase.model_validate(_case(trace={"latency_ms": 120.5, "cost_usd": 0.003}))
    assert case.trace == CaseTrace(latency_ms=120.5, cost_usd=0.003)
    with pytest.raises(ValidationError):
        CaseTrace(latency_ms=-1.0)


def test_trace_rejects_unknown_field():
    with pytest.raises(ValidationError):
        EvalCase.model_validate(_case(trace={"latency_ms": 1.0, "gpu": 2}))


def test_milestone_requires_exactly_one_target():
    assert Milestone(tool="search").tool == "search"
    assert Milestone(output_contains="done").output_contains == "done"
    with pytest.raises(ValidationError):
        Milestone(description="neither")
    with pytest.raises(ValidationError):
        Milestone(tool="search", output_contains="done")


def test_milestones_parse_on_case():
    case = EvalCase.model_validate(
        _case(milestones=[{"tool": "search"}, {"output_contains": "answer", "description": "ans"}])
    )
    assert [m.tool for m in case.milestones] == ["search", None]
    assert case.milestones[1].output_contains == "answer"
