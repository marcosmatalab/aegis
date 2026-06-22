"""F4 golden anchors: the new cases drive the trajectory metrics, the
Agent-as-a-Judge, and the CLEAR Cost/Latency dimensions (L1/L2/L3 oracles for
them are checked generically in test_evals_golden.py)."""

from __future__ import annotations

import asyncio

from aegis.evals.dataset import load_golden
from aegis.evals.judge.agent import MockTrajectoryJudge
from aegis.evals.judge.mock import MockJudge
from aegis.evals.runner import run_suite
from aegis.evals.trajectory import progress_rate

_BY_ID = {c.id: c for c in load_golden()}


def _assess(case):
    return asyncio.run(MockTrajectoryJudge().assess(case))


def test_looping_agent_is_flagged_as_loop():
    v = _assess(_BY_ID["looping-agent"])
    assert v.has_loop is True
    assert v.redundant_steps == 2


def test_error_recovery_is_detected():
    v = _assess(_BY_ID["error-recovery"])
    assert v.recovered_from_error is True
    assert v.has_loop is False


def test_redundant_step_is_not_a_loop():
    v = _assess(_BY_ID["redundant-step"])
    assert v.has_loop is False
    assert v.redundant_steps == 1


def test_partial_milestones_progress_is_two_thirds():
    pr = progress_rate(_BY_ID["partial-milestones"])
    assert pr.breakdown["total"] == 3
    assert round(pr.score, 3) == 0.667


def test_traced_case_makes_clear_cost_latency_synthetic():
    report = run_suite([_BY_ID["traced-calc"]], MockJudge())
    assert report.clear["cost"]["status"] == "synthetic"
    assert report.clear["cost"]["value"] == 0.002
    assert report.clear["latency"]["value"] == 120.0
