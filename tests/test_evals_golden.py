"""Validates the golden dataset: every case's `expected` oracle must match the
real scorers (L1/L3 deterministic; L2 via the deterministic MockJudge). This
makes the golden self-checking and proves the levels are independent."""

from __future__ import annotations

import asyncio

import pytest

from aegis.evals.dataset import load_golden
from aegis.evals.judge.mock import MockJudge
from aegis.evals.l1_session import score_l1
from aegis.evals.l2_trace import score_l2
from aegis.evals.l3_tool import score_l3

CASES = load_golden()
_IDS = [c.id for c in CASES]


def test_golden_loads_and_is_varied():
    assert len(CASES) >= 20
    # positive AND negative coverage at every level
    assert any(c.expected.l1_goal_met for c in CASES)
    assert any(not c.expected.l1_goal_met for c in CASES)
    assert any(c.expected.l3_trajectory_match for c in CASES)
    assert any(not c.expected.l3_trajectory_match for c in CASES)
    l2 = [c for c in CASES if c.expected.l2_faithful is not None]
    assert any(c.expected.l2_faithful for c in l2)
    assert any(not c.expected.l2_faithful for c in l2)


def test_levels_are_independent():
    # at least one case per cross-level disagreement direction
    assert any(c.expected.l1_goal_met and not c.expected.l3_trajectory_match for c in CASES)
    assert any(not c.expected.l1_goal_met and c.expected.l3_trajectory_match for c in CASES)
    assert any(
        c.expected.l1_goal_met
        and c.expected.l2_faithful is False
        and c.expected.l3_trajectory_match
        for c in CASES
    )


@pytest.mark.parametrize("case", CASES, ids=_IDS)
def test_l1_matches_oracle(case):
    assert score_l1(case).passed is case.expected.l1_goal_met


@pytest.mark.parametrize("case", CASES, ids=_IDS)
def test_l3_matches_oracle(case):
    assert score_l3(case).passed is case.expected.l3_trajectory_match


@pytest.mark.parametrize("case", CASES, ids=_IDS)
def test_l2_matches_oracle(case):
    res = asyncio.run(score_l2(case, MockJudge()))
    if case.expected.l2_faithful is None:
        assert res.breakdown.get("applicable") is False
    else:
        assert res.passed is case.expected.l2_faithful


_BY_ID = {c.id: c for c in CASES}


def test_l2_sub_metrics_are_isolated_and_can_diverge():
    # single-sub cases exercise exactly one sub-metric (a relevancy<->faithfulness
    # swap would flip these), and the divergence case has differing sub-scores.
    faith = asyncio.run(score_l2(_BY_ID["faithfulness-only"], MockJudge())).breakdown
    assert "faithfulness" in faith and "relevancy" not in faith

    rel = asyncio.run(score_l2(_BY_ID["relevancy-only"], MockJudge())).breakdown
    assert "relevancy" in rel and "faithfulness" not in rel

    div = asyncio.run(score_l2(_BY_ID["relevant-but-partly-unfaithful"], MockJudge())).breakdown
    assert div["relevancy"] != div["faithfulness"]
