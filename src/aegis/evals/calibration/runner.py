"""Run the configured judge over the calibration set and build a kappa report.

Mirrors ``evals.runner._score_all``: all async judging happens in ONE event loop
(a real provider's httpx client binds to a single loop and cannot span the
per-case ``asyncio.run`` calls), cases are scored SEQUENTIALLY IN ORDER (no
``gather``, so ``verdict[i]`` pairs with ``case[i]`` for the strict-zip in
``compute_calibration``), and the judge is closed on shutdown in a ``finally``
that swallows close errors so they can never mask a scoring exception.

The judge is built by the caller (outside the loop); its client is created
lazily on the first ``complete()`` inside the loop — the same lifecycle the eval
suite uses.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from aegis.evals.calibration.kappa import PASS_THRESHOLD
from aegis.evals.calibration.models import CalibrationCase
from aegis.evals.calibration.report import CalibrationReport, compute_calibration
from aegis.evals.judge.base import Judge, JudgeVerdict

log = logging.getLogger("aegis.evals.calibration")


async def _aclose_quietly(judge: Judge) -> None:
    """Close the judge, swallowing (logging) any close error so it can never mask
    a real scoring exception. A local copy (not ``runner._aclose_quietly``) keeps
    F5 decoupled from the F3/F4 runner internals."""
    try:
        await judge.aclose()
    except Exception as exc:  # noqa: BLE001 - close errors must not break the run
        log.warning("calibration judge aclose failed: %s", type(exc).__name__)


async def _score_one(case: CalibrationCase, judge: Judge) -> JudgeVerdict:
    # Each row carries exactly its own grounding (relevancy -> reference,
    # faithfulness -> context); the other is None by the model invariant, so we
    # can pass both straight through without branching.
    return await judge.score(
        case.criterion, case.output, reference=case.reference, context=case.context
    )


async def _score_all(cases: Sequence[CalibrationCase], judge: Judge) -> list[JudgeVerdict]:
    try:
        return [await _score_one(case, judge) for case in cases]
    finally:
        await _aclose_quietly(judge)


def run_calibration(
    cases: Sequence[CalibrationCase],
    judge: Judge,
    *,
    threshold: float = PASS_THRESHOLD,
    created: int = 0,
) -> CalibrationReport:
    """Score the calibration set with ``judge`` (one event loop, judge closed on
    shutdown) and compute the per-criterion + global agreement report."""
    verdicts = asyncio.run(_score_all(cases, judge))
    return compute_calibration(
        cases, verdicts, judge=judge.name, threshold=threshold, created=created
    )
