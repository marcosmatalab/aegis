"""Shared helpers to read and rewrite message content for guardrails.

ONE implementation used by both input and output checks, so detection and
redaction are consistent across sides (the design review flagged divergent
flattening otherwise). Handles the OpenAI content union:
``str | list[dict] (multimodal parts) | None``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

Content = str | list[dict[str, Any]] | None


def flatten_content(content: Content) -> str:
    """Flatten message content to plain text for scanning.

    str -> itself; list of parts -> the text parts joined by a space; None -> "".
    Non-text / malformed parts are skipped without error.
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    parts = (p.get("text", "") for p in content if isinstance(p, dict))
    return " ".join(t for t in parts if t).strip()


def map_content(content: Content, fn: Callable[[str], str]) -> Content:
    """Apply a text transform ``fn`` to content while preserving its shape.

    str -> ``fn(str)``; list[dict] -> each text part's ``text`` replaced by
    ``fn(text)`` (non-text / non-dict parts kept verbatim); None -> None.
    """
    if content is None:
        return None
    if isinstance(content, str):
        return fn(content)
    new_parts: list[Any] = []
    for part in content:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            new_parts.append({**part, "text": fn(part["text"])})
        else:
            new_parts.append(part)
    return new_parts
