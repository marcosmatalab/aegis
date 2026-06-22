"""L2 judge layer — abstract Judge + deterministic MockJudge (offline default).

The real LLM-as-judge (G-Eval / ensemble) and the ``build_judge`` factory are
added alongside this module; the judge is directional, never ground truth.
"""

from aegis.evals.judge.base import Judge, JudgeVerdict
from aegis.evals.judge.mock import MockJudge

__all__ = ["Judge", "JudgeVerdict", "MockJudge"]
