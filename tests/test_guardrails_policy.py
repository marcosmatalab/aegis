"""Tests for the allow/deny policy engine."""

from __future__ import annotations

from aegis.guardrails.policy import evaluate


def test_no_rules_allows():
    assert evaluate("anything goes", deny=[], allow=[]).action == "allow"


def test_deny_rule_blocks_with_rule_id():
    decision = evaluate("this mentions a forbidden topic", deny=[r"forbidden"], allow=[])
    assert decision.action == "deny"
    assert decision.rule_id == "forbidden"


def test_deny_is_case_insensitive():
    assert evaluate("FORBIDDEN", deny=[r"forbidden"], allow=[]).action == "deny"


def test_non_matching_deny_allows():
    assert evaluate("totally fine", deny=[r"forbidden"], allow=[]).action == "allow"


def test_allow_overrides_deny():
    # text matches both deny and allow -> allow wins
    decision = evaluate("forbidden but whitelisted", deny=[r"forbidden"], allow=[r"whitelisted"])
    assert decision.action == "allow"
    assert decision.rule_id is None


def test_first_matching_deny_rule_reported():
    decision = evaluate("alpha beta", deny=[r"zzz", r"beta", r"alpha"], allow=[])
    assert decision.action == "deny"
    assert decision.rule_id == "beta"


def test_invalid_regex_falls_back_to_literal_substring():
    # "(" is an invalid regex; must not crash and should match literally
    assert evaluate("a (b c", deny=["("], allow=[]).action == "deny"
    assert evaluate("a b c", deny=["("], allow=[]).action == "allow"


def test_empty_text():
    assert evaluate("", deny=[r"x"], allow=[]).action == "allow"
