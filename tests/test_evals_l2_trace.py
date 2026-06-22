"""Tests for the judge-backed L2 trace scorer (deterministic MockJudge)."""

from __future__ import annotations

import asyncio

from aegis.evals.judge.mock import MockJudge
from aegis.evals.l2_trace import score_l2
from aegis.evals.models import EvalCase


def _case(final_output, reference=None, context=None):
    return EvalCase.model_validate(
        {
            "id": "c1",
            "user_goal": "g",
            "input_messages": [{"role": "user", "content": "hi"}],
            "reference_answer": reference,
            "context": context or [],
            "actual": {"final_output": final_output, "tool_calls": []},
            "expected": {
                "l1_goal_met": True,
                "l2_faithful": True if (reference or context) else None,
                "l3_trajectory_match": True,
            },
        }
    )


def _l2(case):
    return asyncio.run(score_l2(case, MockJudge()))


def test_relevant_and_faithful_passes():
    res = _l2(_case("cat sat", reference="cat sat", context=["cat sat"]))
    assert res.score == 1.0
    assert res.passed is True
    assert res.breakdown["relevancy"] == 1.0
    assert res.breakdown["faithfulness"] == 1.0


def test_relevancy_and_faithfulness_are_independent():
    # output is faithful to context but irrelevant to the reference
    res = _l2(_case("dog ran", reference="cat sat", context=["dog ran"]))
    assert res.breakdown["relevancy"] == 0.0
    assert res.breakdown["faithfulness"] == 1.0  # independent signals


def test_unfaithful_lowers_score():
    res = _l2(_case("cat flew", reference="cat flew", context=["cat sat"]))
    assert res.breakdown["relevancy"] == 1.0
    assert res.breakdown["faithfulness"] == 0.5


def test_not_applicable_without_reference_or_context():
    res = _l2(_case("anything"))
    assert res.breakdown["applicable"] is False
    assert res.passed is False


def test_empty_string_reference_treated_as_absent():
    # symmetric with an empty context list -> L2 not applicable, not a hard 0
    res = _l2(_case("anything", reference=""))
    assert res.breakdown["applicable"] is False


def test_only_reference_uses_relevancy_only():
    res = _l2(_case("cat sat", reference="cat sat"))
    assert "relevancy" in res.breakdown
    assert "faithfulness" not in res.breakdown
    assert res.score == 1.0


def test_only_context_uses_faithfulness_only():
    res = _l2(_case("cat sat", context=["cat sat on the mat"]))
    assert "faithfulness" in res.breakdown
    assert "relevancy" not in res.breakdown


def test_per_case_threshold_is_diagnostic_not_the_gate():
    # mean(0.0 relevancy, 0.5 faithfulness) = 0.25 < 0.5 -> fails the per-case mark
    res = _l2(_case("dog flew", reference="cat sat", context=["dog ran fast"]))
    assert res.breakdown["relevancy"] == 0.0
    assert res.passed is False
