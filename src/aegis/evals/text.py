"""Small deterministic text helpers for the eval scorers (offline, no deps).

Kept independent of the guardrails package so evals and guardrails stay
decoupled. Matching is whole-word / token-based (not raw substring), so e.g.
``must_include="cat"`` is NOT satisfied by "catastrophe" and "24" is not
satisfied by "1024".
"""

from __future__ import annotations

import re
from typing import Any

_WORD = re.compile(r"\w+", re.UNICODE)

# A tiny stopword set used by the judge's overlap heuristics (not by L1).
_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "to",
        "of",
        "and",
        "or",
        "in",
        "on",
        "at",
        "for",
        "it",
        "its",
        "this",
        "that",
        "with",
        "as",
        "by",
        "from",
        "but",
        "if",
        "then",
        "so",
        "do",
    }
)


def flatten(content: str | list[dict[str, Any]] | None) -> str:
    """Flatten message/output content (str / multimodal parts / None) to text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = (p.get("text", "") for p in content if isinstance(p, dict))
    return " ".join(t for t in parts if t).strip()


def tokens(text: str) -> list[str]:
    return [t.lower() for t in _WORD.findall(text)]


def content_tokens(text: str) -> set[str]:
    """Lowercased word tokens minus stopwords (for overlap/grounding heuristics)."""
    return {t for t in tokens(text) if t not in _STOPWORDS}


def phrase_present(text: str, phrase: str) -> bool:
    """True if ``phrase``'s tokens appear as a contiguous run in ``text``'s tokens."""
    needle = tokens(phrase)
    if not needle:
        return False
    hay = tokens(text)
    n = len(needle)
    return any(hay[i : i + n] == needle for i in range(len(hay) - n + 1))
