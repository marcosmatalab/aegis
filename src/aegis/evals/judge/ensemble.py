"""Ensemble judge — runs N member judges and aggregates their scores.

A diverse panel reduces single-judge variance/bias. Aggregation is mean or
median. Members all run at temperature 0 (deterministic) in this design.
"""

from __future__ import annotations

import statistics
from typing import Any

from aegis.evals.judge.base import Judge, JudgeVerdict


class EnsembleJudge(Judge):
    name = "ensemble"

    def __init__(self, members: list[Judge], aggregate: str = "mean", *, provider: Any = None):
        if not members:
            raise ValueError("ensemble needs at least one member judge")
        if aggregate not in {"mean", "median"}:
            raise ValueError(f"aggregate must be 'mean' or 'median', got {aggregate!r}")
        self.members = members
        self.aggregate = aggregate
        # The members share ONE provider/client; the ensemble owns closing it once.
        self.provider = provider

    async def score(
        self,
        criteria: str,
        output: str,
        *,
        reference: str | None = None,
        context: list[str] | None = None,
    ) -> JudgeVerdict:
        scores: list[float] = []
        any_parse_failed = False
        for member in self.members:
            verdict = await member.score(criteria, output, reference=reference, context=context)
            scores.append(verdict.score)
            any_parse_failed = any_parse_failed or verdict.parse_failed
        agg = statistics.median(scores) if self.aggregate == "median" else statistics.fmean(scores)
        reason = (
            f"ensemble({self.aggregate}) of {len(scores)} judges: {[round(s, 3) for s in scores]}"
        )
        # If any member parse-failed, surface it on the aggregate too (auditable).
        return JudgeVerdict(agg, reason, criteria, self.name, parse_failed=any_parse_failed)

    async def aclose(self) -> None:
        # Members share one provider; close it exactly once (idempotent anyway).
        if self.provider is not None:
            await self.provider.aclose()
