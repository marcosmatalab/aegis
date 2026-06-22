"""Tests for the eval runner, aggregation, and JSON persistence."""

from __future__ import annotations

import json

from aegis.evals.dataset import load_golden
from aegis.evals.judge.mock import MockJudge
from aegis.evals.models import EvalCase
from aegis.evals.persistence import write_report
from aegis.evals.runner import run_suite


def _case(case_id, **overrides):
    body = {
        "id": case_id,
        "user_goal": "g",
        "input_messages": [{"role": "user", "content": "hi"}],
        "expected_trajectory": [],
        "success_criteria": {"must_include": ["ok"]},
        "actual": {"final_output": "ok", "tool_calls": []},
        "expected": {"l1_goal_met": True, "l2_faithful": None, "l3_trajectory_match": True},
    }
    body.update(overrides)
    return EvalCase.model_validate(body)


# --- aggregation ------------------------------------------------------------ #
def test_runs_over_golden_suite():
    cases = load_golden()
    report = run_suite(cases, MockJudge(), suite="golden")
    assert report.case_count == len(cases)
    assert set(report.levels) == {"L1", "L2", "L3"}
    assert 0.0 <= report.overall_score <= 1.0
    # some golden cases are L2 not-applicable, so L2 scored < total
    assert report.levels["L2"].scored < report.case_count
    assert len(report.cases) == len(cases)


def test_empty_level_excluded_from_overall():
    # no case has a reference/context -> L2 never applies -> excluded
    cases = [_case("a"), _case("b")]
    report = run_suite(cases, MockJudge())
    assert "L2" not in report.levels
    assert set(report.levels) == {"L1", "L3"}
    # overall is the mean of L1 and L3 only (both 1.0 here)
    assert report.overall_score == 1.0


def test_aggregate_counts_passes():
    cases = [
        _case("pass", success_criteria={"must_include": ["ok"]}),
        _case("fail", success_criteria={"must_include": ["missing"]}),
    ]
    report = run_suite(cases, MockJudge())
    assert report.levels["L1"].scored == 2
    assert report.levels["L1"].passed == 1


def test_deterministic_report():
    cases = load_golden()
    a = run_suite(cases, MockJudge(), created=0).to_dict()
    b = run_suite(cases, MockJudge(), created=0).to_dict()
    assert a == b


# --- F4: trajectory metrics, agent-judge, CLEAR ----------------------------- #
def _tool_case(case_id, **overrides):
    base = {
        "expected_trajectory": [{"name": "t", "arguments": {}}],
        "actual": {"final_output": "ok", "tool_calls": [{"name": "t", "arguments": {}}]},
    }
    base.update(overrides)
    return _case(case_id, **base)


def test_report_includes_trajectory_and_agent_judge_per_case():
    report = run_suite([_tool_case("a")], MockJudge())
    row = report.cases[0]
    assert set(row.trajectory) == {
        "tool_correctness",
        "trajectory_accuracy",
        "progress_rate",
        "t_eval",
    }
    assert "score" in row.agent_judge and "has_loop" in row.agent_judge


def test_report_includes_clear_five_dimensions():
    report = run_suite([_case("a")], MockJudge())
    assert set(report.clear) == {"cost", "latency", "efficiency", "accuracy", "reliability"}
    assert report.clear["accuracy"]["score"] == report.overall_score
    # no trace on the case -> cost/latency are honest placeholders
    assert report.clear["cost"]["status"] == "placeholder"
    assert report.clear["latency"]["status"] == "placeholder"


def test_clear_cost_latency_synthetic_with_trace():
    report = run_suite([_tool_case("a", trace={"cost_usd": 0.01, "latency_ms": 50.0})], MockJudge())
    assert report.clear["cost"]["status"] == "synthetic"
    assert report.clear["cost"]["value"] == 0.01
    assert report.clear["latency"]["value"] == 50.0
    assert report.clear["cost"]["score"] is None  # no budget passed


def test_clear_budget_normalizes_score():
    report = run_suite(
        [_tool_case("a", trace={"latency_ms": 250.0})],
        MockJudge(),
        latency_budget_ms=1000.0,
    )
    assert report.clear["latency"]["score"] == 0.75


def test_suite_trajectory_aggregate_present():
    report = run_suite([_tool_case("a")], MockJudge())
    assert report.trajectory["tool_correctness"]["mean_score"] == 1.0
    assert report.trajectory["tool_correctness"]["scored"] == 1


def test_agent_judge_flags_loop_in_report():
    case = _tool_case(
        "loopy",
        actual={"final_output": "ok", "tool_calls": [{"name": "t"}, {"name": "t"}]},
    )
    report = run_suite([case], MockJudge())
    assert report.cases[0].agent_judge["has_loop"] is True


# --- persistence ------------------------------------------------------------ #
def test_write_report_roundtrips_json(tmp_path):
    report = run_suite([_case("a")], MockJudge(), suite="unit", created=123)
    out = write_report(report, tmp_path / "sub" / "report.json")
    assert out.exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["suite"] == "unit"
    assert loaded["created"] == 123
    assert loaded["judge"] == "mock"
    assert loaded["overall_score"] == report.overall_score
    assert loaded["cases"][0]["id"] == "a"
