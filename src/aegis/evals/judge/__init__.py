"""L2 judge layer — abstract Judge, deterministic MockJudge (offline default),
the real G-Eval-inspired judge (reuses the Anthropic provider), an ensemble, and
a settings factory.

The judge is DIRECTIONAL — a signal validated against human labels (Cohen's κ, a
later phase), never ground truth.
"""

from aegis.evals.judge.base import Judge, JudgeVerdict
from aegis.evals.judge.ensemble import EnsembleJudge
from aegis.evals.judge.factory import build_judge
from aegis.evals.judge.geval import GEvalJudge, JudgeNotConfiguredError
from aegis.evals.judge.mock import MockJudge

__all__ = [
    "EnsembleJudge",
    "GEvalJudge",
    "Judge",
    "JudgeNotConfiguredError",
    "JudgeVerdict",
    "MockJudge",
    "build_judge",
]
