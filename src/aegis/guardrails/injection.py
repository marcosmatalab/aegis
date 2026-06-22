"""Deterministic prompt-injection detection, mapped to OWASP LLM01.

Design bias: a guardrail that blocks legitimate traffic is worse than a
permissive one, so every pattern is HIGH-CONFIDENCE and narrow:

  * an override directive needs the verb (ignore/disregard/forget/override/
    bypass) AND a "previous/above/all/any" qualifier AND an instruction noun —
    so "ignore the noise", "disregard my earlier email" or "the previous
    instructions were unclear" do NOT match;
  * a system-prompt leak needs an imperative verb (reveal/show/print/…) AND a
    possessive (your/the/its) before "system prompt/instructions" — so
    "what is a system prompt?" does NOT match;
  * role-injection markers match ONLY chat-template tokens
    (<|im_start|>system, [INST], <<SYS>>) — never a bare "system:" that appears
    in code, logs or prose;
  * jailbreak personas need an explicit jailbreak keyword (DAN, developer mode,
    jailbroken, …) — so "act as a translator" does NOT match.

The detector is pure and deterministic (no model, no network).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_NOUN = r"(?:instructions?|prompts?|rules?|directions?|commands?|guidelines?|constraints?)"
_QUALIFIER = r"(?:previous|prior|above|preceding|earlier|foregoing|all|any)"
_POSSESSIVE = r"(?:your|the|its)"
_SYSTEM_TARGET = (
    r"(?:system\s+(?:prompt|message)|system\s+instructions?|"
    r"initial\s+(?:prompt|instructions?)|original\s+(?:prompt|instructions?)|"
    r"hidden\s+(?:prompt|instructions?))"
)

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "override_instructions",
        re.compile(
            rf"\b(?:ignore|disregard|forget|override|bypass)\b"
            rf"(?:\s+\w+){{0,3}}?\s+\b{_QUALIFIER}\b"
            rf"(?:\s+\w+){{0,3}}?\s+\b{_NOUN}\b",
            re.IGNORECASE,
        ),
    ),
    (
        "reveal_system_prompt",
        re.compile(
            rf"\b(?:reveal|show|print|repeat|output|expose|divulge|disclose|leak|copy)\b"
            rf"(?:\s+\w+){{0,3}}?\s+\b{_POSSESSIVE}\b"
            rf"(?:\s+\w+){{0,2}}?\s+\b{_SYSTEM_TARGET}\b",
            re.IGNORECASE,
        ),
    ),
    (
        "role_injection_marker",
        re.compile(
            r"(?:<\|im_start\|>\s*system|<\|system\|>|\[/?INST\]|<<\s*SYS\s*>>|\[/?SYSTEM\])",
            re.IGNORECASE,
        ),
    ),
    (
        "jailbreak_persona",
        re.compile(
            r"\b(?:you\s+are\s+now|from\s+now\s+on|act\s+as|pretend\s+to\s+be|roleplay\s+as)\b"
            r"(?:\s+\w+){0,4}?\s+"
            r"\b(?:dan|do\s+anything\s+now|developer\s+mode|jailbroken|jailbreak|"
            r"unrestricted|without\s+(?:any\s+)?restrictions?|no\s+longer\s+bound)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "new_policy_override",
        re.compile(
            r"\b(?:new|updated|revised)\s+(?:policy|rule|instruction|directive)\b\s*:?"
            r"(?:\s+\w+){0,4}?\s+"
            r"\b(?:ignore|bypass|disable|execute|reveal|leak|without\s+confirmation)\b",
            re.IGNORECASE,
        ),
    ),
]


@dataclass(frozen=True, slots=True)
class InjectionVerdict:
    hit: bool
    pattern_id: str | None = None


def scan(text: str) -> InjectionVerdict:
    """Return a verdict for a single piece of text. First matching pattern wins."""
    for pattern_id, rx in _PATTERNS:
        if rx.search(text):
            return InjectionVerdict(hit=True, pattern_id=pattern_id)
    return InjectionVerdict(hit=False)
