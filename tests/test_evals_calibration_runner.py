"""run_calibration over an injected scripted judge — offline, no key, no network.

MockJudge can never emit a parse_failed verdict, so the runner's exclusion +
degenerate routing and the close-never-masks-scoring contract are exercised here
with a scripted Judge returning canned verdicts (including one parse_failed).
"""

from __future__ import annotations

import asyncio

import pytest

from aegis.evals.calibration.models import CalibrationCase
from aegis.evals.calibration.runner import run_calibration
from aegis.evals.judge.base import Judge, JudgeVerdict


def _case(cid: str, ctype: str, label: str) -> CalibrationCase:
    score = 1.0 if label == "pass" else 0.0
    row = {
        "id": cid,
        "criterion_type": ctype,
        "criterion": "c",
        "output": "o",
        "human_label": label,
        "human_score": score,
    }
    row |= (
        {"reference": "r", "context": None}
        if ctype == "relevancy"
        else {
            "reference": None,
            "context": ["c"],
        }
    )
    return CalibrationCase.model_validate(row)


def _v(score: float, *, parse_failed: bool = False) -> JudgeVerdict:
    return JudgeVerdict(score, "reason", "crit", "scripted", parse_failed=parse_failed)


class _ScriptedJudge(Judge):
    """Returns canned verdicts in call order (scoring is sequential and in case
    order, so this also pins verdict[i] <-> case[i])."""

    name = "scripted"

    def __init__(self, verdicts):
        self._it = iter(verdicts)
        self.closed = 0
        self.loops: list[int] = []

    async def score(self, criteria, output, *, reference=None, context=None):
        self.loops.append(id(asyncio.get_running_loop()))
        return next(self._it)

    async def aclose(self):
        self.closed += 1


def test_run_calibration_one_loop_closes_once_and_excludes_parse_failed():
    cases = [
        _case("cal-rel-01", "relevancy", "pass"),
        _case("cal-rel-02", "relevancy", "fail"),
        _case("cal-fai-01", "faithfulness", "pass"),
        _case("cal-fai-02", "faithfulness", "fail"),
    ]
    judge = _ScriptedJudge([_v(0.9), _v(0.1), _v(0.9, parse_failed=True), _v(0.1)])
    report = run_calibration(cases, judge, created=7)

    assert report.judge == "scripted" and report.created == 7
    assert report.n_cases == 4 and report.n_parse_failed == 1
    # all four calls ran on ONE event loop; judge closed exactly once
    assert len(judge.loops) == 4 and len(set(judge.loops)) == 1
    assert judge.closed == 1
    # relevancy: (pass,pass)+(fail,fail) -> kappa 1.0; faithfulness: one excluded,
    # the surviving (fail,fail) is single-class -> kappa undefined (None)
    assert report.per_criterion["relevancy"].result.kappa == pytest.approx(1.0)
    assert report.per_criterion["faithfulness"].result.kappa is None
    assert report.per_criterion["faithfulness"].n_parse_failed == 1
    assert report.global_.result.kappa == pytest.approx(1.0)


class _ScoringBoomJudge(Judge):
    name = "boom"

    async def score(self, criteria, output, *, reference=None, context=None):
        raise RuntimeError("scoring boom")

    async def aclose(self):
        self.closed = getattr(self, "closed", 0) + 1


def test_scoring_error_propagates_and_close_still_runs():
    judge = _ScoringBoomJudge()
    with pytest.raises(RuntimeError, match="scoring boom"):
        run_calibration([_case("cal-rel-01", "relevancy", "pass")], judge)
    assert judge.closed == 1  # close ran in finally, did not mask the error


class _CloseBoomJudge(Judge):
    name = "close-boom"

    async def score(self, criteria, output, *, reference=None, context=None):
        return _v(0.9)

    async def aclose(self):
        raise RuntimeError("close boom")


def test_close_error_on_clean_run_is_swallowed():
    report = run_calibration([_case("cal-rel-01", "relevancy", "pass")], _CloseBoomJudge())
    assert report.n_cases == 1  # the run succeeded despite the close failure
