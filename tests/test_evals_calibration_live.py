"""Live judge-calibration smoke test — the ONLY calibration test that hits the
real Anthropic API.

SKIPPED unless BOTH ``ANTHROPIC_API_KEY`` is set AND the optional ``[anthropic]``
SDK is installed; CI runs neither, so it self-skips and the suite stays green
offline. SPEND CAP: a 2-case subset (one relevancy + one faithfulness) at a low
max_tokens — the full 30-case calibration run is manual. It guards that the real
wire path produces a well-formed CalibrationReport on ONE event loop.

Override the model with ``AEGIS_LIVE_TEST_MODEL`` (default: current Claude Opus).
"""

from __future__ import annotations

import os

import pytest

from aegis.evals.calibration.dataset import load_calibration
from aegis.evals.calibration.runner import run_calibration
from aegis.evals.judge.factory import build_judge
from aegis.gateway.config import Settings
from aegis.gateway.providers.anthropic_provider import is_available

_KEY = os.getenv("ANTHROPIC_API_KEY")
_MODEL = os.getenv("AEGIS_LIVE_TEST_MODEL", "anthropic/claude-opus-4-8")

pytestmark = pytest.mark.skipif(
    not _KEY or not is_available(),
    reason="requires ANTHROPIC_API_KEY and the optional [anthropic] extra",
)


def test_live_calibration_produces_a_well_formed_report():
    settings = Settings(_env_file=None).model_copy(
        update={"judge_backend": "geval", "judge_model": _MODEL, "judge_max_tokens": 256}
    )
    cases = load_calibration()
    subset = [
        next(c for c in cases if c.criterion_type == "relevancy"),
        next(c for c in cases if c.criterion_type == "faithfulness"),
    ]

    # build judge outside, run_calibration drives one event loop + closes it
    report = run_calibration(subset, build_judge(settings))

    assert report.judge == "geval"
    assert report.n_cases == 2
    for section in (report.global_, *report.per_criterion.values()):
        r = section.result
        assert r.kappa is None or -1.0 <= r.kappa <= 1.0
        assert r.p_o is None or 0.0 <= r.p_o <= 1.0
        assert r.n_valid + section.n_parse_failed == section.n_cases
