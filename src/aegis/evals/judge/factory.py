"""Selects the L2 judge from settings (mirrors F1's provider factory)."""

from __future__ import annotations

from aegis.evals.judge.base import Judge
from aegis.evals.judge.ensemble import EnsembleJudge
from aegis.evals.judge.geval import GEvalJudge, model_split
from aegis.evals.judge.mock import MockJudge
from aegis.gateway.config import Settings
from aegis.gateway.upstream import Provider, build_provider


def _build_judge_provider(settings: Settings) -> Provider:
    """Build the ONE provider the real judge(s) reuse. Built via the same
    ``build_provider`` as the gateway, so the judge shares that machinery and a
    single cached client. Missing key/SDK surfaces as ProviderNotConfiguredError,
    which the eval CLI catches and turns into a clean exit (never an offline crash)."""
    provider_name, _ = model_split(settings.judge_model)
    return build_provider(provider_name, settings)


def build_judge(settings: Settings) -> Judge:
    """Return the configured judge. ``mock`` is the keyless offline default;
    ``geval``/``ensemble`` build ONE real provider and reuse it across all calls
    (the ensemble's members share that single client)."""
    backend = settings.judge_backend
    if backend == "mock":
        return MockJudge()
    if backend == "geval":
        return GEvalJudge(settings, _build_judge_provider(settings))
    if backend == "ensemble":
        provider = _build_judge_provider(settings)
        members = [GEvalJudge(settings, provider) for _ in range(settings.judge_ensemble_size)]
        return EnsembleJudge(members, provider=provider)
    raise ValueError(f"unknown judge backend {backend!r}")
