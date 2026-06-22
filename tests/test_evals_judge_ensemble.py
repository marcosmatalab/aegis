"""Tests for the ensemble judge aggregation (deterministic fixed-score members)."""

from __future__ import annotations

import asyncio

import pytest

from aegis.evals.judge.base import Judge, JudgeVerdict
from aegis.evals.judge.ensemble import EnsembleJudge


class _FixedJudge(Judge):
    def __init__(self, value: float):
        self.name = f"fixed-{value}"
        self.value = value

    async def score(self, criteria, output, *, reference=None, context=None):
        return JudgeVerdict(self.value, "fixed", criteria, self.name)


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


def test_empty_ensemble_rejected():
    with pytest.raises(ValueError):
        EnsembleJudge([])


def test_invalid_aggregate_rejected():
    with pytest.raises(ValueError):
        EnsembleJudge([_FixedJudge(0.5)], aggregate="mode")
