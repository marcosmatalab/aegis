"""GEvalJudge real-path behavior with an injected fake provider (no key, no SDK,
no network): request shape, score parsing, the never-raise neutral fallback on
messy/empty/None replies, and provider close."""

from __future__ import annotations

import asyncio

import pytest

from aegis.evals.judge.geval import GEvalJudge
from aegis.gateway.config import Settings
from aegis.gateway.schemas import (
    ChatCompletionResponse,
    Choice,
    ResponseMessage,
    Usage,
)


class _FakeJudgeProvider:
    """Duck-typed provider: returns a canned assistant reply, records the request,
    and counts aclose(). ``reply_content`` may be str | list | None to exercise
    the coercion path."""

    name = "fake-judge"

    def __init__(self, reply_content):
        self.reply_content = reply_content
        self.requests: list = []
        self.closed = 0

    async def complete(self, request) -> ChatCompletionResponse:
        self.requests.append(request)
        return ChatCompletionResponse(
            id="judge-1",
            created=1,
            model=request.model,
            choices=[
                Choice(
                    index=0,
                    message=ResponseMessage(role="assistant", content=self.reply_content),
                    finish_reason="stop",
                )
            ],
            usage=Usage(prompt_tokens=1, completion_tokens=1, total_tokens=2),
        )

    async def aclose(self) -> None:
        self.closed += 1


def _judge(reply_content) -> tuple[GEvalJudge, _FakeJudgeProvider]:
    provider = _FakeJudgeProvider(reply_content)
    judge = GEvalJudge(Settings(_env_file=None), provider)
    return judge, provider


def _score(judge, **kw):
    return asyncio.run(judge.score("relevancy: is it relevant?", "the output", **kw))


# --- request shape ---------------------------------------------------------- #
def test_request_uses_bare_model_system_and_budget():
    judge, provider = _judge('{"score": 0.8, "reasoning": "ok"}')
    _score(judge, reference="ref")
    req = provider.requests[0]
    assert req.model == "claude-opus-4-8"  # BARE id (no 'anthropic/' prefix)
    assert req.messages[0].role == "system"
    assert req.messages[1].role == "user"
    assert req.max_tokens == 1024  # judge_max_tokens spend cap
    assert req.temperature == 0.0


# --- happy parsing ---------------------------------------------------------- #
def test_score_parses_clean_json():
    judge, _ = _judge('{"reasoning": "good", "score": 0.75}')
    v = _score(judge, reference="ref")
    assert v.score == 0.75 and v.parse_failed is False
    assert v.judge == "geval"


def test_score_parses_fenced_json():
    judge, _ = _judge('```json\n{"score": 0.6, "reasoning": "fenced"}\n```')
    v = _score(judge, reference="ref")
    assert v.score == 0.6 and v.parse_failed is False


def test_score_clamps_out_of_range_is_not_a_parse_failure():
    judge, _ = _judge('{"score": 1.7, "reasoning": "too high"}')
    v = _score(judge, reference="ref")
    assert v.score == 1.0 and v.parse_failed is False  # clamped, not a failure


# --- never-raise neutral fallback ------------------------------------------- #
def test_unparseable_reply_falls_back_to_neutral_flagged():
    judge, _ = _judge("totally not json, no score anywhere")
    v = _score(judge, reference="ref")
    assert v.score == 0.5 and v.parse_failed is True


def test_missing_score_falls_back_to_neutral_flagged():
    judge, _ = _judge('{"reasoning": "no score field"}')
    v = _score(judge, reference="ref")
    assert v.score == 0.5 and v.parse_failed is True


def test_empty_reply_falls_back_to_neutral_flagged():
    judge, _ = _judge("")
    v = _score(judge, reference="ref")
    assert v.score == 0.5 and v.parse_failed is True


def test_none_content_coerces_and_falls_back_neutral():
    # a None (or structured) reply must coerce to '' and parse-fail, never raise
    judge, _ = _judge(None)
    v = _score(judge, reference="ref")
    assert v.score == 0.5 and v.parse_failed is True


def test_non_numeric_score_falls_back_to_neutral_flagged():
    judge, _ = _judge('{"score": "high", "reasoning": "x"}')
    v = _score(judge, reference="ref")
    assert v.score == 0.5 and v.parse_failed is True


def test_overflowing_integer_score_falls_back_to_neutral_not_crash():
    # a degenerate huge-int score must NOT escape the never-raise contract
    judge, _ = _judge('{"score": ' + "9" * 400 + "}")
    v = _score(judge, reference="ref")
    assert v.score == 0.5 and v.parse_failed is True


# --- upstream errors PROPAGATE (a failure to get a judgment, not a neutral) -- #
class _RaisingProvider:
    name = "raising"

    async def complete(self, request):
        raise RuntimeError("upstream 503")

    async def aclose(self) -> None:
        pass


def test_upstream_error_propagates_and_is_not_swallowed_as_neutral():
    judge = GEvalJudge(Settings(_env_file=None), _RaisingProvider())
    # an upstream/transport failure must propagate (not become a neutral 0.5) — the
    # narrow except wraps ONLY parsing, never provider.complete()
    with pytest.raises(RuntimeError, match="upstream 503"):
        _score(judge, reference="ref")


# --- close ------------------------------------------------------------------ #
def test_aclose_closes_the_provider():
    judge, provider = _judge('{"score": 0.5}')
    asyncio.run(judge.aclose())
    assert provider.closed == 1
