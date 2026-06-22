"""Offline eval runner: scores a suite of cases at L1/L2/L3, computes the F4
trajectory metrics + Agent-as-a-Judge verdict per case, aggregates the CLEAR
dimensions per run, and assembles a report.

L1 and L3 are deterministic; L2 and the Agent-as-a-Judge go through their (default
Mock) judges. Levels with zero applicable cases are EXCLUDED from the overall mean
(so an absent or not-applicable level neither inflates nor deflates the aggregate).
The overall score is the mean of the per-level mean scores, and it is what CLEAR
reports as Accuracy.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from aegis.evals.clear import CaseSignal, ClearDimension, compute_clear
from aegis.evals.judge.agent import MockTrajectoryJudge, TrajectoryJudge, TrajectoryVerdict
from aegis.evals.judge.base import Judge
from aegis.evals.l1_session import score_l1
from aegis.evals.l2_trace import score_l2
from aegis.evals.l3_tool import score_l3
from aegis.evals.models import EvalCase
from aegis.evals.report import CaseReport, LevelAggregate, Report
from aegis.evals.result import ScoreResult
from aegis.evals.trajectory import MetricScore, score_trajectory

_TRAJECTORY_KEYS = ("tool_correctness", "trajectory_accuracy", "progress_rate", "t_eval")


def _result_dict(result: ScoreResult) -> dict:
    return {
        "score": result.score,
        "passed": result.passed,
        "reasons": list(result.reasons),
        "breakdown": result.breakdown,
    }


def _metric_dict(m: MetricScore) -> dict:
    return {"score": m.score, "applicable": m.applicable, "breakdown": m.breakdown}


def _trajectory_dict(metrics: dict[str, MetricScore]) -> dict:
    return {key: _metric_dict(metrics[key]) for key in _TRAJECTORY_KEYS}


def _verdict_dict(v: TrajectoryVerdict) -> dict:
    return {
        "score": v.score,
        "reasoning": v.reasoning,
        "findings": list(v.findings),
        "has_loop": v.has_loop,
        "redundant_steps": v.redundant_steps,
        "recovered_from_error": v.recovered_from_error,
        "judge": v.judge,
    }


def _clear_dict(clear: dict[str, ClearDimension]) -> dict:
    return {
        name: {
            "name": d.name,
            "status": d.status,
            "applicable": d.applicable,
            "score": d.score,
            "value": d.value,
            "unit": d.unit,
            "basis": d.basis,
        }
        for name, d in clear.items()
    }


async def _judge_case(
    case: EvalCase, judge: Judge, traj_judge: TrajectoryJudge
) -> tuple[ScoreResult, TrajectoryVerdict]:
    """Run the two async judges for one case in a single event loop."""
    l2 = await score_l2(case, judge)
    verdict = await traj_judge.assess(case)
    return l2, verdict


def run_suite(
    cases: Sequence[EvalCase],
    judge: Judge,
    traj_judge: TrajectoryJudge | None = None,
    *,
    suite: str = "default",
    created: int = 0,
    latency_budget_ms: float | None = None,
    cost_budget_usd: float | None = None,
) -> Report:
    traj_judge = traj_judge or MockTrajectoryJudge()
    rows: list[CaseReport] = []
    scored: dict[str, list[ScoreResult]] = {"L1": [], "L2": [], "L3": []}
    metrics_per_case: list[dict[str, MetricScore]] = []
    signals: list[CaseSignal] = []

    for case in cases:
        l1 = score_l1(case)
        l3 = score_l3(case)
        l2, verdict = asyncio.run(_judge_case(case, judge, traj_judge))
        metrics = score_trajectory(case)
        metrics_per_case.append(metrics)

        rows.append(
            CaseReport(
                id=case.id,
                tags=list(case.tags),
                l1=_result_dict(l1),
                l2=_result_dict(l2),
                l3=_result_dict(l3),
                trajectory=_trajectory_dict(metrics),
                agent_judge=_verdict_dict(verdict),
            )
        )
        scored["L1"].append(l1)
        scored["L3"].append(l3)
        l2_applicable = bool(l2.breakdown.get("applicable", False))
        if l2_applicable:
            scored["L2"].append(l2)

        signals.append(
            CaseSignal(
                l1_passed=l1.passed,
                l3_passed=l3.passed,
                l2_applicable=l2_applicable,
                l2_passed=l2.passed,
                exact_calls=metrics["tool_correctness"].breakdown["exact"],
                actual_calls=len(case.actual.tool_calls),
                latency_ms=case.trace.latency_ms if case.trace else None,
                cost_usd=case.trace.cost_usd if case.trace else None,
            )
        )

    levels: dict[str, LevelAggregate] = {}
    for level, results in scored.items():
        if not results:
            continue
        mean = sum(r.score for r in results) / len(results)
        passed = sum(1 for r in results if r.passed)
        levels[level] = LevelAggregate(level, mean, passed, len(results))

    overall = sum(la.mean_score for la in levels.values()) / len(levels) if levels else 0.0
    clear = compute_clear(
        signals,
        overall,
        latency_budget_ms=latency_budget_ms,
        cost_budget_usd=cost_budget_usd,
    )

    return Report(
        suite=suite,
        judge=judge.name,
        case_count=len(cases),
        created=created,
        levels=levels,
        overall_score=overall,
        cases=rows,
        clear=_clear_dict(clear),
        trajectory=_aggregate_trajectory(metrics_per_case),
    )


def _aggregate_trajectory(metrics_per_case: list[dict[str, MetricScore]]) -> dict:
    """Suite-level mean of each trajectory metric over the cases where it applies."""
    aggregate: dict[str, dict] = {}
    for key in _TRAJECTORY_KEYS:
        applicable = [m[key].score for m in metrics_per_case if m[key].applicable]
        if applicable:
            aggregate[key] = {
                "mean_score": sum(applicable) / len(applicable),
                "scored": len(applicable),
            }
    return aggregate
