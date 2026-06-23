"""Tests for the ensemble judge aggregation (deterministic fixed-score members)."""

from __future__ import annotations

import asyncio

import pytest

from aegis.evals.judge.base import Judge, JudgeVerdict
from aegis.evals.judge.ensemble import EnsembleJudge


class _FixedJudge(Judge):
    def __init__(self, value: float, *, parse_failed: bool = False):
        self.name = f"fixed-{value}"
        self.value = value
        self.parse_failed = parse_failed

    async def score(self, criteria, output, *, reference=None, context=None):
        return JudgeVerdict(
            self.value, "fixed", criteria, self.name, parse_failed=self.parse_failed
        )


def _run(judge):
    return asyncio.run(judge.score("relevancy", "x", reference="y"))


def test_ensemble_mean():
    judge = EnsembleJudge([_FixedJudge(0.2), _FixedJudge(0.8), _FixedJudge(0.5)], aggregate="mean")
    assert round(_run(judge).score, 3) == 0.5


def test_ensemble_median():
    judge = EnsembleJudge(
        [_FixedJudge(0.1), _FixedJudge(0.9), _FixedJudge(0.4)], aggregate="median"
    )
    assert _run(judge).score == 0.4


def test_ensemble_identical_members():
    judge = EnsembleJudge([_FixedJudge(0.7), _FixedJudge(0.7)])
    assert _run(judge).score == 0.7


def test_ensemble_median_even_count():
    # median of an even count = mean of the two middle values (0.4, 0.6) -> 0.5
    judge = EnsembleJudge(
        [_FixedJudge(0.2), _FixedJudge(0.4), _FixedJudge(0.6), _FixedJudge(0.9)],
        aggregate="median",
    )
    assert _run(judge).score == 0.5


def test_parse_failed_bubbles_when_any_member_failed():
    judge = EnsembleJudge([_FixedJudge(0.4), _FixedJudge(0.8, parse_failed=True)])
    assert _run(judge).parse_failed is True


def test_parse_failed_false_when_all_members_clean():
    judge = EnsembleJudge([_FixedJudge(0.4), _FixedJudge(0.8)])
    assert _run(judge).parse_failed is False


def test_empty_ensemble_rejected():
    with pytest.raises(ValueError):
        EnsembleJudge([])


def test_invalid_aggregate_rejected():
    with pytest.raises(ValueError):
        EnsembleJudge([_FixedJudge(0.5)], aggregate="mode")
