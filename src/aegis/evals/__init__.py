"""Aegis F3 — an offline 3-level eval engine (L1 session / L2 trace / L3 tool).

Deterministic and keyless by default: L1 and L3 are scored without any LLM, and
L2 is backed by a deterministic MockJudge, so the whole suite runs offline with
no API keys. The LLM-as-judge is treated as DIRECTIONAL — a signal to be
validated against human labels (a later phase), never ground truth. L2
faithfulness in particular is a lexical-containment heuristic, not real
entailment (see the judge module).
"""

from aegis.evals.dataset import DEFAULT_GOLDEN_PATH, GoldenDatasetError, load_golden
from aegis.evals.models import (
    CandidateOutput,
    EvalCase,
    ExpectedVerdict,
    SuccessCriteria,
    ToolCall,
)

__all__ = [
    "DEFAULT_GOLDEN_PATH",
    "CandidateOutput",
    "EvalCase",
    "ExpectedVerdict",
    "GoldenDatasetError",
    "SuccessCriteria",
    "ToolCall",
    "load_golden",
]
