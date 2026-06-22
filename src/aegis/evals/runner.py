"""Offline eval runner: scores a suite of cases at L1/L2/L3 and assembles a report.

L1 and L3 are deterministic; L2 goes through the (default Mock) judge. Levels
with zero applicable cases are EXCLUDED from the overall mean (so an absent or
not-applicable level neither inflates nor deflates the aggregate). The overall
score is the mean of the per-level mean scores.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from aegis.evals.judge.base import Judge
from aegis.evals.l1_session import score_l1
from aegis.evals.l2_trace import score_l2
from aegis.evals.l3_tool import score_l3
from aegis.evals.models import EvalCase
from aegis.evals.report import CaseReport, LevelAggregate, Report
from aegis.evals.result import ScoreResult


def _result_dict(result: ScoreResult) -> dict:
    return {
        "score": result.score,
        "passed": result.passed,
        "reasons": list(result.reasons),
        "breakdown": result.breakdown,
    }


def run_suite(
    cases: Sequence[EvalCase], judge: Judge, *, suite: str = "default", created: int = 0
) -> Report:
    rows: list[CaseReport] = []
    scored: dict[str, list[ScoreResult]] = {"L1": [], "L2": [], "L3": []}

    for case in cases:
        l1 = score_l1(case)
        l3 = score_l3(case)
        l2 = asyncio.run(score_l2(case, judge))
        rows.append(
            CaseReport(
                id=case.id,
                tags=list(case.tags),
                l1=_result_dict(l1),
                l2=_result_dict(l2),
                l3=_result_dict(l3),
            )
        )
        scored["L1"].append(l1)
        scored["L3"].append(l3)
        if l2.breakdown.get("applicable", False):
            scored["L2"].append(l2)

    levels: dict[str, LevelAggregate] = {}
    for level, results in scored.items():
        if not results:
            continue
        mean = sum(r.score for r in results) / len(results)
        passed = sum(1 for r in results if r.passed)
        levels[level] = LevelAggregate(level, mean, passed, len(results))

    overall = sum(la.mean_score for la in levels.values()) / len(levels) if levels else 0.0
    return Report(
        suite=suite,
        judge=judge.name,
        case_count=len(cases),
        created=created,
        levels=levels,
        overall_score=overall,
        cases=rows,
    )
