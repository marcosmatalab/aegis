"""Deterministic prompt-injection detection, mapped to OWASP LLM01.

Design bias: a guardrail that blocks legitimate traffic is worse than a
permissive one, so every pattern is HIGH-CONFIDENCE and narrow. The detector
covers the most-abused, low-false-positive attack classes:

  * override directives — verb (ignore/disregard/forget/override/bypass/reset)
    + a "previous/above/all/your" qualifier + an instruction noun, OR the same
    verb directly targeting the system prompt;
  * system-prompt leaks — an imperative verb (reveal/show/tell/give/…) before a
    possessive + "system prompt/instructions", an interrogative "what … your …
    instructions", or a "repeat/print … (words|text|everything) … above" leak;
  * role-injection markers — ONLY chat-template tokens (<|im_start|>system,
    [INST], <<SYS>>); never a bare "system:";
  * jailbreak personas — require an explicit keyword (DAN, developer mode, …);
  * "new policy/instructions: … ignore/reveal …" override directives;
  * a Spanish override directive ("ignora … instrucciones anteriores").

Benign code, prose, and technical text (e.g. "what is a system prompt?",
"print the text file", "show me the rules of chess") are designed to pass — see
the large false-positive regression suite. Pure and deterministic.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_NOUN = r"(?:instructions?|prompts?|rules?|directions?|commands?|guidelines?|constraints?)"
_QUALIFIER = r"(?:previous|prior|above|preceding|earlier|foregoing|all|any|your)"
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
            rf"\b(?:ignore|disregard|forget|override|bypass|reset)\b"
            rf"(?:\s+\w+){{0,3}}?\s+\b{_QUALIFIER}\b"
            rf"(?:\s+\w+){{0,3}}?\s+\b{_NOUN}\b",
            re.IGNORECASE,
        ),
    ),
    (
        "override_system_prompt",
        re.compile(
            rf"\b(?:ignore|disregard|forget|override|bypass|reset)\b"
            rf"(?:\s+\w+){{0,3}}?\s+{_SYSTEM_TARGET}\b",
            re.IGNORECASE,
        ),
    ),
    (
        "reveal_system_prompt",
        re.compile(
            rf"\b(?:reveal|show|print|repeat|output|expose|divulge|disclose|leak|copy|tell|give|share|spell)\b"
            rf"(?:\s+\w+){{0,3}}?\s+{_POSSESSIVE}(?:\s+\w+){{0,2}}?\s+{_SYSTEM_TARGET}\b",
            re.IGNORECASE,
        ),
    ),
    (
        "reveal_your_directives",
        re.compile(
            r"\b(?:reveal|show|print|repeat|output|tell|give|share|spell)\b"
            r"(?:\s+\w+){0,3}?\s+your(?:\s+\w+){0,2}?\s+\b(?:instructions?|rules?|guidelines?|prompt)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "interrogative_leak",
        re.compile(
            rf"\b(?:what|which)\b(?:\s+\w+){{0,5}}?\s+your"
            rf"(?:\s+\w+){{0,2}}?\s+\b(?:{_SYSTEM_TARGET}|instructions?|rules?|guidelines?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "leak_repeat_above",
        re.compile(
            r"\b(?:repeat|print|output|echo|reproduce|spell\s+out)\b"
            r"(?:\s+\w+){0,4}?\s+\b(?:words?|text|everything|prompt|instructions?|message)\b"
            r"(?:\s+\w+){0,3}?\s+\b(?:above|verbatim|preceding|word\s+for\s+word)\b",
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
            r"\b(?:new|updated|revised)\s+"
            r"(?:policy|policies|rule|rules|instruction|instructions|directive|directives)\b\s*:?"
            r"(?:\s+\w+){0,4}?\s+"
            r"\b(?:ignore|bypass|disable|execute|reveal|leak|reset|without\s+confirmation)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "override_es",
        re.compile(
            r"\b(?:ignora|olvida|descarta|desestima|omite)\b"
            r"(?:\s+\w+){0,3}?\s+\b(?:instrucciones|reglas|[óo]rdenes|indicaciones|directrices)\b"
            r"(?:\s+\w+){0,2}?\s+\b(?:anteriores|previas|previos|precedentes|de\s+arriba)\b",
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
