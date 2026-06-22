"""Tests for the basic deterministic toxicity detector."""

from __future__ import annotations

from aegis.guardrails.toxicity import scan


def test_threat_blocks_on_its_own():
    v = scan("kill yourself")
    assert v.hit is True
    assert v.score >= 1.0


def test_insult_blocks_at_default_threshold():
    v = scan("you are an idiot")
    assert v.hit is True
    assert v.score == 0.6


def test_mild_phrase_below_threshold_does_not_block():
    # "shut up" weighs 0.4, below the default 0.5 threshold
    v = scan("shut up")
    assert v.hit is False
    assert v.score == 0.4


def test_benign_text_not_flagged():
    v = scan("this is a stupid bug but I will fix the code")
    assert v.hit is False
    assert v.score == 0.0
    assert v.terms == ()


def test_empty_text_never_hits_even_at_zero_threshold():
    v = scan("", threshold=0.0)
    assert v.hit is False
    assert v.score == 0.0


def test_threshold_is_configurable():
    # raise the bar so a single insult no longer blocks
    assert scan("you are a loser", threshold=0.9).hit is False
    # lower the bar so a mild phrase blocks
    assert scan("shut up", threshold=0.3).hit is True


def test_score_is_capped_at_one():
    v = scan("kill yourself and kys, go die")
    assert v.score == 1.0
    assert v.hit is True
