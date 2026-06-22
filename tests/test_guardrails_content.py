"""Tests for shared guardrail content helpers and the GuardrailResult type."""

from __future__ import annotations

from aegis.guardrails.content import flatten_content, map_content
from aegis.guardrails.result import GuardrailResult


# --- flatten_content -------------------------------------------------------- #
def test_flatten_str():
    assert flatten_content("hello") == "hello"


def test_flatten_none():
    assert flatten_content(None) == ""


def test_flatten_list_parts():
    content = [
        {"type": "text", "text": "a"},
        {"type": "image_url", "image_url": {}},
        {"type": "text", "text": "b"},
    ]
    assert flatten_content(content) == "a b"


def test_flatten_empty_list():
    assert flatten_content([]) == ""


# --- map_content ------------------------------------------------------------ #
def test_map_content_str():
    assert map_content("hello world", str.upper) == "HELLO WORLD"


def test_map_content_none():
    assert map_content(None, str.upper) is None


def test_map_content_list_preserves_nontext_parts():
    parts = [
        {"type": "text", "text": "hi"},
        {"type": "image_url", "image_url": {"url": "x"}},
    ]
    out = map_content(parts, lambda s: s.replace("hi", "bye"))
    assert out == [
        {"type": "text", "text": "bye"},
        {"type": "image_url", "image_url": {"url": "x"}},
    ]


def test_map_content_list_mixed_and_missing_text():
    # parts without a string 'text' or non-dict entries pass through untouched
    parts = [{"type": "text", "text": "a"}, {"foo": "bar"}, "raw"]
    out = map_content(parts, str.upper)
    assert out == [{"type": "text", "text": "A"}, {"foo": "bar"}, "raw"]


# --- GuardrailResult -------------------------------------------------------- #
def test_result_allow():
    r = GuardrailResult.allow("input")
    assert r.blocked is False
    assert r.stage == "input"
    assert r.redacted_request is None
    assert r.checks_run == ()


def test_result_block():
    r = GuardrailResult.block("output", reason="leak", code="pii_leak", param="content")
    assert r.blocked is True
    assert r.stage == "output"
    assert r.code == "pii_leak"
    assert r.param == "content"
    assert r.type == "guardrail_blocked"
