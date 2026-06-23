"""G-Eval-INSPIRED LLM-as-judge — light Chain-of-Thought, direct parsed score.

The judge justifies briefly then emits a compact JSON ``{reasoning, score}`` at
low temperature; the score is read DIRECTLY from the reply. This is NOT canonical
G-Eval: it does not do logprob-weighted scoring (the Anthropic API exposes no
per-token logprobs), so it carries more variance than logprob G-Eval — mitigated
by temperature 0 and, ultimately, validated by Cohen's-kappa calibration vs human
labels (a later phase). The judge is DIRECTIONAL, not ground truth.

It REUSES the Anthropic provider (build a ChatCompletionRequest + provider.complete),
never a second client. A messy/unparseable reply NEVER raises: ``score`` falls
back to a NEUTRAL score flagged ``parse_failed=True`` (auditable in the report).
The pure helpers (``model_split``, ``parse_verdict``, prompt building) stay pure
and raising; the never-raise wrapper lives in ``GEvalJudge.score``.
"""

from __future__ import annotations

import json
import math
import re
from typing import Any

from aegis.evals.judge.base import Judge, JudgeVerdict
from aegis.evals.judge.prompts import G_EVAL_SYSTEM, G_EVAL_TEMPLATE
from aegis.evals.text import flatten
from aegis.gateway.config import Settings
from aegis.gateway.schemas import ChatCompletionRequest, ChatCompletionResponse
from aegis.gateway.upstream import Provider

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
_NEUTRAL_SCORE = 0.5  # == L2_THRESHOLD: a parse failure neither passes nor fails on its merits


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


def _reply_text(response: ChatCompletionResponse) -> str:
    """Coerce the assistant reply to plain text (str | parts | None -> str), so a
    None/structured reply parse-fails to a neutral score instead of raising."""
    if not response.choices:
        return ""
    return flatten(response.choices[0].message.content)


class GEvalJudge(Judge):
    name = "geval"

    def __init__(self, settings: Settings, provider: Provider):
        self.settings = settings
        self.provider_name, self.model = model_split(settings.judge_model)
        self.temperature = settings.judge_temperature
        self.max_tokens = settings.judge_max_tokens
        self.provider = provider  # reused across calls; the SAME cached client

    async def score(
        self,
        criteria: str,
        output: str,
        *,
        reference: str | None = None,
        context: list[str] | None = None,
    ) -> JudgeVerdict:
        request = ChatCompletionRequest(
            model=self.model,  # bare model id; the provider sends it as-is
            messages=[
                {"role": "system", "content": G_EVAL_SYSTEM},
                {"role": "user", "content": build_prompt(criteria, output, reference, context)},
            ],
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        # Upstream/transport errors PROPAGATE (a failure to GET a judgment, surfaced
        # by the runner/CLI) — only an UNPARSEABLE reply falls back to neutral.
        response = await self.provider.complete(request)
        try:
            score, reasoning = parse_verdict(_reply_text(response))
        except (ValueError, TypeError) as exc:
            return JudgeVerdict(
                _NEUTRAL_SCORE,
                f"parse failure ({type(exc).__name__}): neutral fallback",
                criteria,
                self.name,
                parse_failed=True,
            )
        return JudgeVerdict(score, reasoning, criteria, self.name)

    async def aclose(self) -> None:
        await self.provider.aclose()
