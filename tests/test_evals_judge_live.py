"""Live G-Eval-inspired judge integration test — the ONLY test that hits the real
Anthropic API for the judge.

SKIPPED unless BOTH ``ANTHROPIC_API_KEY`` is set AND the optional ``[anthropic]``
SDK is installed; CI runs neither, so it self-skips and the suite stays green
offline. SPEND CAP: exactly ONE judge call (one provider.complete) at a low
max_tokens — the bulk suite runs on the deterministic MockJudge. It guards that
the real wire path returns a parseable, in-range verdict (parse_failed is False),
which only holds if the bounded compact-JSON prompt fits the token budget.

Override the model with ``AEGIS_LIVE_TEST_MODEL`` (default: current Claude Opus).
"""

from __future__ import annotations

import asyncio
import os

import pytest

from aegis.evals.judge.geval import GEvalJudge
from aegis.gateway.config import Settings
from aegis.gateway.providers.anthropic_provider import is_available
from aegis.gateway.upstream import build_provider

_KEY = os.getenv("ANTHROPIC_API_KEY")
_MODEL = os.getenv("AEGIS_LIVE_TEST_MODEL", "anthropic/claude-opus-4-8")

pytestmark = pytest.mark.skipif(
    not _KEY or not is_available(),
    reason="requires ANTHROPIC_API_KEY and the optional [anthropic] extra",
)


def test_live_geval_scores_one_case():
    settings = Settings(_env_file=None).model_copy(
        update={"judge_model": _MODEL, "judge_max_tokens": 256}
    )

    async def _run():
        # build + score + close all on ONE event loop (the client binds to it)
        judge = GEvalJudge(settings, build_provider("anthropic", settings))
        try:
            return await judge.score(
                "relevancy: is the output relevant to and consistent with the reference?",
                "Paris is the capital of France.",
                reference="The capital of France is Paris.",
            )
        finally:
            await judge.aclose()

    verdict = asyncio.run(_run())
    assert 0.0 <= verdict.score <= 1.0
    # the bounded compact-JSON verdict fits in 256 tokens, so it must parse cleanly
    assert verdict.parse_failed is False
