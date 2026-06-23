"""G-Eval (Chain-of-Thought) LLM-as-judge — reasons before scoring.

The judge reasons step by step then emits JSON ``{reasoning, score}`` at
temperature 0. The actual LLM call goes through a provider and is a CLEAR STUB
in F3 — no paid SDK is imported and ``score`` raises a clear error directing
callers to the mock backend. The deterministic, pure helpers (``model_split``,
``parse_verdict``, prompt building) ARE implemented and tested so the wire
contract is locked for when a real provider lands (a later phase, alongside
Cohen's-kappa calibration vs human labels).
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

from aegis.evals.judge.base import Judge, JudgeVerdict
from aegis.evals.judge.prompts import G_EVAL_TEMPLATE
from aegis.gateway.config import Settings

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


class JudgeNotConfiguredError(RuntimeError):
    """Raised when the real G-Eval judge is selected but no provider is wired."""


def model_split(judge_model: str) -> tuple[str, str]:
    """Split a ``provider/model`` id into (provider, model)."""
    provider, sep, model = judge_model.partition("/")
    if not sep or not provider or not model:
        raise ValueError(f"judge_model must be 'provider/model', got {judge_model!r}")
    return provider, model


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def _strip_code_fences(raw: str) -> str:
    """Return the inside of the first ```...``` (or ```json) block, else ``raw``.

    LLM replies often wrap the JSON in a markdown code fence; pulling the fenced
    content out first makes the first-brace/last-brace scan robust even when the
    surrounding prose contains braces."""
    match = _FENCE_RE.search(raw)
    return match.group(1).strip() if match else raw


def _extract_json(raw: str) -> dict[str, Any]:
    text = _strip_code_fences(raw)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError(f"no JSON object in judge reply: {raw[:120]!r}")
    return json.loads(text[start : end + 1])


def parse_verdict(raw: str) -> tuple[float, str]:
    """Parse a judge JSON reply into (clamped score, reasoning).

    Pure and RAISING: robust to a numeric or string score, to markdown code
    fences, and to prose surrounding the JSON, but raises ``ValueError`` on
    unparseable input / missing / non-numeric / non-finite score. The never-raise
    neutral fallback lives in ``GEvalJudge.score`` (which wraps this).
    """
    data = _extract_json(raw)
    score = data.get("score")
    if isinstance(score, str):
        score = float(score.strip())
    if isinstance(score, bool) or not isinstance(score, (int, float)):
        raise ValueError(f"judge reply has no numeric score: {raw[:120]!r}")
    value = float(score)
    # json.loads accepts NaN/Infinity, and "nan"/"inf" parse via float() — reject
    # them so a degenerate judge reply can't produce a non-finite score.
    if not math.isfinite(value):
        raise ValueError(f"judge score is not finite: {raw[:120]!r}")
    return _clamp01(value), str(data.get("reasoning", ""))


def build_prompt(
    criteria: str, output: str, reference: str | None, context: list[str] | None
) -> str:
    return G_EVAL_TEMPLATE.format(
        criteria=criteria,
        output=output or "",
        reference=reference or "N/A",
        context="\n".join(context or []) or "N/A",
    )


class GEvalJudge(Judge):
    name = "geval"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.provider_name, self.model = model_split(settings.judge_model)
        self.temperature = settings.judge_temperature

    async def score(
        self,
        criteria: str,
        output: str,
        *,
        reference: str | None = None,
        context: list[str] | None = None,
    ) -> JudgeVerdict:
        # F3 stub: building the prompt works, but no real provider is wired.
        _ = build_prompt(criteria, output, reference, context)
        raise JudgeNotConfiguredError(
            "The G-Eval judge needs a real LLM provider, which is not wired in F3. "
            "Set AEGIS_JUDGE_BACKEND=mock to run evals offline."
        )
