"""Tests for the deterministic MockJudge heuristics."""

from __future__ import annotations

import asyncio

from aegis.evals.judge.mock import MockJudge


def _score(criteria, output, **kw):
    return asyncio.run(MockJudge().score(criteria, output, **kw))


# --- relevancy (token-overlap F1 vs reference) ------------------------------ #
def test_relevancy_identical_is_one():
    v = _score("relevancy", "the cat sat", reference="the cat sat")
    assert v.score == 1.0


def test_relevancy_partial():
    # out content tokens {cat}; ref {cat, sat} -> P=1, R=0.5 -> F1≈0.667
    v = _score("relevancy", "the cat", reference="the cat sat")
    assert round(v.score, 3) == 0.667


def test_relevancy_disjoint_is_zero():
    assert _score("relevancy", "dog", reference="cat").score == 0.0


def test_relevancy_empty_output_is_zero():
    assert _score("relevancy", "", reference="cat").score == 0.0


# --- faithfulness (lexical containment in context) -------------------------- #
def test_faithfulness_fully_grounded():
    v = _score("faithfulness", "cat sat", context=["the cat sat on the mat"])
    assert v.score == 1.0


def test_faithfulness_partially_grounded():
    # out {cat, flew}; ctx {cat, sat} -> 1/2 grounded
    v = _score("faithfulness", "cat flew", context=["cat sat"])
    assert v.score == 0.5


def test_faithfulness_reordered_copy_scores_one_documented_limitation():
    # reordered copy of the context is "faithful" under lexical containment —
    # the intentional, documented weakness of the deterministic mock
    v = _score("faithfulness", "sat cat", context=["cat sat"])
    assert v.score == 1.0


def test_faithfulness_no_context_is_zero():
    assert _score("faithfulness", "cat", context=[]).score == 0.0


def test_faithfulness_empty_output_is_zero():
    assert _score("faithfulness", "", context=["cat sat"]).score == 0.0


# --- determinism ------------------------------------------------------------ #
def test_deterministic_across_calls():
    a = _score("relevancy", "the cat sat on the mat", reference="a cat on the mat")
    b = _score("relevancy", "the cat sat on the mat", reference="a cat on the mat")
    assert a == b
