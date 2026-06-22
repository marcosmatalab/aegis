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
