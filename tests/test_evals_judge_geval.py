"""Tests for the G-Eval judge helpers, stub, and the judge factory."""

from __future__ import annotations

import asyncio

import pytest

from aegis.evals.judge import (
    EnsembleJudge,
    GEvalJudge,
    JudgeNotConfiguredError,
    MockJudge,
    build_judge,
)
from aegis.evals.judge.geval import build_prompt, model_split, parse_verdict
from aegis.gateway.config import Settings


# --- model_split ------------------------------------------------------------ #
def test_model_split_valid():
    assert model_split("anthropic/claude-opus-4-6") == ("anthropic", "claude-opus-4-6")


@pytest.mark.parametrize("bad", ["noslash", "/model", "provider/", ""])
def test_model_split_invalid(bad):
    with pytest.raises(ValueError):
        model_split(bad)


# --- parse_verdict ---------------------------------------------------------- #
def test_parse_numeric_score():
    score, reasoning = parse_verdict('{"reasoning": "good", "score": 0.8}')
    assert score == 0.8
    assert reasoning == "good"


def test_parse_string_score():
    assert parse_verdict('{"score": "0.42", "reasoning": "x"}')[0] == 0.42


def test_parse_score_clamped():
    assert parse_verdict('{"score": 1.7}')[0] == 1.0
    assert parse_verdict('{"score": -0.5}')[0] == 0.0


def test_parse_tolerates_surrounding_prose():
    raw = 'Here is my judgment:\n{"reasoning": "ok", "score": 0.6}\nThanks!'
    assert parse_verdict(raw)[0] == 0.6


def test_parse_strips_json_code_fence():
    raw = '```json\n{"reasoning": "fenced", "score": 0.7}\n```'
    score, reasoning = parse_verdict(raw)
    assert score == 0.7 and reasoning == "fenced"


def test_parse_strips_bare_code_fence_with_prose_braces():
    # a plain ``` fence, with braces in the surrounding prose that would otherwise
    # confuse a naive first{/last} scan
    raw = 'Result (format {k:v}):\n```\n{"score": 0.9}\n```\ndone.'
    assert parse_verdict(raw)[0] == 0.9


def test_judge_verdict_parse_failed_defaults_false():
    from aegis.evals.judge.base import JudgeVerdict

    assert JudgeVerdict(0.5, "x").parse_failed is False


def test_parse_missing_score_raises():
    with pytest.raises(ValueError):
        parse_verdict('{"reasoning": "no score here"}')


def test_parse_no_json_raises():
    with pytest.raises(ValueError):
        parse_verdict("totally not json")


def test_parse_rejects_bool_score():
    with pytest.raises(ValueError):
        parse_verdict('{"score": true}')


@pytest.mark.parametrize(
    "raw",
    [
        '{"score": NaN}',
        '{"score": Infinity}',
        '{"score": -Infinity}',
        '{"score": "nan"}',
        '{"score": "inf"}',
    ],
)
def test_parse_rejects_non_finite_scores(raw):
    with pytest.raises(ValueError):
        parse_verdict(raw)


def test_parse_nested_brace_json_object():
    score, _ = parse_verdict('{"reasoning": "x", "score": 0.5, "meta": {"k": 1}}')
    assert score == 0.5


def test_extract_json_reversed_braces_raises():
    with pytest.raises(ValueError):
        parse_verdict("} score 0.5 {")


# --- prompt structure (Chain-of-Thought) ------------------------------------ #
def test_build_prompt_is_chain_of_thought():
    prompt = build_prompt("relevancy", "the answer", reference="ref", context=["ctx"])
    assert "step by step" in prompt
    assert "relevancy" in prompt and "the answer" in prompt and "ref" in prompt
    # reasoning must be requested BEFORE the score in the JSON contract
    assert prompt.index("reasoning") < prompt.index("score")


# --- real-judge stub -------------------------------------------------------- #
def test_geval_score_is_a_clear_stub():
    judge = GEvalJudge(Settings(_env_file=None))
    with pytest.raises(JudgeNotConfiguredError, match="not wired in F3"):
        asyncio.run(judge.score("relevancy", "x", reference="y"))


# --- factory ---------------------------------------------------------------- #
def test_factory_mock():
    assert isinstance(build_judge(Settings(_env_file=None, judge_backend="mock")), MockJudge)


def test_factory_geval():
    assert isinstance(build_judge(Settings(_env_file=None, judge_backend="geval")), GEvalJudge)


def test_factory_ensemble_size():
    judge = build_judge(Settings(_env_file=None, judge_backend="ensemble", judge_ensemble_size=4))
    assert isinstance(judge, EnsembleJudge)
    assert len(judge.members) == 4
