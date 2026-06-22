"""Selects the L2 judge from settings (mirrors F1's provider factory)."""

from __future__ import annotations

from aegis.evals.judge.base import Judge
from aegis.evals.judge.ensemble import EnsembleJudge
from aegis.evals.judge.geval import GEvalJudge
from aegis.evals.judge.mock import MockJudge
from aegis.gateway.config import Settings


def build_judge(settings: Settings) -> Judge:
    """Return the configured judge. ``mock`` is the offline default; ``geval`` and
    ``ensemble`` use the real (stubbed) judge."""
    backend = settings.judge_backend
    if backend == "mock":
        return MockJudge()
    if backend == "geval":
        return GEvalJudge(settings)
    if backend == "ensemble":
        members = [GEvalJudge(settings) for _ in range(settings.judge_ensemble_size)]
        return EnsembleJudge(members)
    raise ValueError(f"unknown judge backend {backend!r}")
