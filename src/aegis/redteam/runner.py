"""Run the attack catalog against the F2 guardrail pipeline — offline + hermetic.

``build_redteam_settings`` constructs Settings with ``_env_file=None`` so a
deployer's ``.env`` / ``AEGIS_*`` vars (e.g. a Presidio engine or a different
toxicity threshold) can never leak in and break determinism; guardrails are on,
the PII engine is regex, and the policy stage gets the bundled deny-list (an empty
list would make it inert). No provider, no judge, no model call, no network — all
async checks run in ONE event loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

from aegis.gateway.config import Settings
from aegis.gateway.schemas import ChatCompletionRequest
from aegis.guardrails.pipeline import GuardrailPipeline, build_pipeline
from aegis.redteam.models import AttackCase
from aegis.redteam.outcome import AttackResult, classify_result
from aegis.redteam.policy_fixture import REDTEAM_DENY
from aegis.redteam.report import RedTeamReport, build_report

_MODEL = "mock/echo-1"  # never forwarded; the pipeline only inspects content


def build_redteam_settings() -> Settings:
    """Hermetic, offline, keyless settings the red-team run always uses."""
    return Settings(
        _env_file=None,
        guardrails_enabled=True,
        gr_pii_engine="regex",
        gr_policy_enabled=True,
        gr_policy_deny=REDTEAM_DENY,
        gr_output_pii_action="block",
    )


async def _score_one(case: AttackCase, pipeline: GuardrailPipeline) -> AttackResult:
    if case.vector == "input":
        request = ChatCompletionRequest(
            model=_MODEL, messages=[{"role": case.role, "content": case.payload}]
        )
        result = await pipeline.check_input(request)
    else:
        result = await pipeline.check_output(case.payload)
    outcome, code = classify_result(result)
    return AttackResult(case, outcome, code)


async def _score_all(
    cases: Sequence[AttackCase], pipeline: GuardrailPipeline
) -> list[AttackResult]:
    return [await _score_one(case, pipeline) for case in cases]


def run_redteam(
    cases: Sequence[AttackCase], *, suite: str = "redteam", created: int = 0
) -> RedTeamReport:
    """Score every attack against the guardrails offline and build the report."""
    pipeline = build_pipeline(build_redteam_settings())
    results = asyncio.run(_score_all(cases, pipeline))
    return build_report(results, suite=suite, created=created)
