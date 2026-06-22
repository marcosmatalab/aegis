"""Deterministic, dependency-free PII detection and redaction (the default engine).

Covers EMAIL_ADDRESS, PHONE_NUMBER (Spanish-format / +CC), CREDIT_CARD (validated
with the Luhn checksum), and the Spanish national IDs ES_NIF (DNI) and ES_NIE —
both validated with the mod-23 control-letter checksum so look-alikes with the
wrong letter are NOT redacted. Matches are resolved in priority order and never
overlap. No model, no network — always available and CI-fast.

Known limitation: detectors are word-boundary anchored, so a sensitive value
embedded inside a longer unbroken digit run (e.g. a card number concatenated
with other digits) may escape. The optional Microsoft Presidio engine handles
such cases better.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CONTROL_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"  # ES DNI/NIE mod-23 table
_NIE_PREFIX = {"X": "0", "Y": "1", "Z": "2"}

_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_NIE = re.compile(r"\b([XYZ])[-]?(\d{7})[-]?([A-Za-z])\b", re.IGNORECASE)
_DNI = re.compile(r"\b(\d{8})[-]?([A-Za-z])\b")
# 13-19 digits, optionally separated by single spaces/hyphens (candidate cards).
_CARD = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
# Spanish-format numbers (start 6-9, 9 digits). To avoid redacting ordinary
# 9-digit numbers (invoice/part/order numbers), a bare contiguous run is NOT
# treated as a phone: a match needs either a +CC prefix or grouping separators.
_PHONE = re.compile(
    r"(?<!\d)(?:"
    r"\+\d{1,3}[ -]?[6-9]\d{2}[ -]?\d{3}[ -]?\d{3}"  # +CC prefix; separators optional
    r"|[6-9]\d{2}[ -]\d{3}[ -]\d{3}"  # national form; separators required
    r")(?!\d)"
)


@dataclass(frozen=True, slots=True)
class PIIMatch:
    entity: str
    start: int
    end: int


def _luhn_ok(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _control_letter_ok(number: int, letter: str) -> bool:
    return _CONTROL_LETTERS[number % 23] == letter.upper()


def detect(text: str) -> list[PIIMatch]:
    """Return non-overlapping PII matches, resolved in priority order."""
    claimed: list[tuple[int, int]] = []
    matches: list[PIIMatch] = []

    def _add(entity: str, start: int, end: int) -> None:
        if any(start < ce and cs < end for cs, ce in claimed):
            return
        claimed.append((start, end))
        matches.append(PIIMatch(entity, start, end))

    for m in _EMAIL.finditer(text):
        _add("EMAIL_ADDRESS", m.start(), m.end())
    for m in _NIE.finditer(text):
        number = int(_NIE_PREFIX[m.group(1).upper()] + m.group(2))
        if _control_letter_ok(number, m.group(3)):
            _add("ES_NIE", m.start(), m.end())
    for m in _DNI.finditer(text):
        if _control_letter_ok(int(m.group(1)), m.group(2)):
            _add("ES_NIF", m.start(), m.end())
    for m in _CARD.finditer(text):
        digits = re.sub(r"\D", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            _add("CREDIT_CARD", m.start(), m.end())
    for m in _PHONE.finditer(text):
        _add("PHONE_NUMBER", m.start(), m.end())

    matches.sort(key=lambda x: x.start)
    return matches


def redact_matches(text: str, matches: list[PIIMatch]) -> tuple[str, tuple[str, ...]]:
    """Replace each match span with ``<ENTITY>``. Shared by every PII engine so
    output is identical regardless of detector. Returns (text, sorted entities)."""
    if not matches:
        return text, ()
    ordered = sorted(matches, key=lambda m: m.start)
    out: list[str] = []
    last = 0
    for m in ordered:
        out.append(text[last : m.start])
        out.append(f"<{m.entity}>")
        last = m.end
    out.append(text[last:])
    return "".join(out), tuple(sorted({m.entity for m in matches}))


def redact(text: str) -> tuple[str, tuple[str, ...]]:
    """Detect and redact PII with the deterministic regex engine."""
    return redact_matches(text, detect(text))


def scan(text: str) -> tuple[str, ...]:
    """Return the sorted set of PII entity types present (no redaction)."""
    return tuple(sorted({m.entity for m in detect(text)}))
