"""Direct tests for the eval text helpers (flatten + unicode whole-word matching)."""

from __future__ import annotations

from aegis.evals.text import content_tokens, flatten, phrase_present


def test_flatten_variants():
    assert flatten(None) == ""
    assert flatten("hi") == "hi"
    assert (
        flatten([{"type": "text", "text": "a"}, {"type": "image_url", "image_url": {"url": "x"}}])
        == "a"
    )
    assert flatten([]) == ""
    assert flatten(["notadict", {"text": "b"}]) == "b"  # non-dict parts skipped


def test_phrase_present_unicode_whole_word():
    assert phrase_present("un café por favor", "café") is True
    assert phrase_present("una cafetería nueva", "café") is False  # not inside a longer word
    assert phrase_present("привет мир", "мир") is True


def test_content_tokens_drops_stopwords():
    assert content_tokens("the cat is on the mat") == {"cat", "mat"}
