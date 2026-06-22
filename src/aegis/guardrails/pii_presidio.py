"""Optional Microsoft Presidio-backed PII engine (richer than the regex default).

Presidio (and its spaCy model) are imported LAZILY — only when this engine is
actually selected — so the base install and CI stay light and fast. Install with
``pip install -e ".[guardrails]"`` plus a spaCy model
(e.g. ``python -m spacy download en_core_web_sm``).

Exposes the same ``redact(text)`` / ``scan(text)`` interface as the regex engine
and reuses the shared ``redact_matches`` so the redacted output is identical.
"""

from __future__ import annotations

import importlib.util
from functools import lru_cache

from aegis.guardrails.pii import PIIMatch, redact_matches

# Presidio entity label -> our placeholder label. Presidio ships ES_NIF but not
# NIE, so we register a custom NIE recognizer below.
_ENTITY_MAP = {
    "EMAIL_ADDRESS": "EMAIL_ADDRESS",
    "PHONE_NUMBER": "PHONE_NUMBER",
    "CREDIT_CARD": "CREDIT_CARD",
    "ES_NIF": "ES_NIF",
    "ES_NIE": "ES_NIE",
}
_ENTITIES = list(_ENTITY_MAP)


def is_available() -> bool:
    return importlib.util.find_spec("presidio_analyzer") is not None


def ensure_available() -> None:
    if not is_available():
        raise RuntimeError(
            "The Presidio PII engine requires the optional dependencies. Install with "
            '`pip install -e ".[guardrails]"` plus a spaCy model '
            "(e.g. `python -m spacy download en_core_web_sm`), or set "
            "AEGIS_GR_PII_ENGINE=regex to use the built-in regex engine."
        )


@lru_cache(maxsize=1)
def _analyzer():
    ensure_available()
    from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer

    engine = AnalyzerEngine()
    nie = PatternRecognizer(
        supported_entity="ES_NIE",
        patterns=[Pattern("nie", r"\b[XYZ][- ]?\d{7}[- ]?[A-Za-z]\b", 0.6)],
    )
    engine.registry.add_recognizer(nie)
    return engine


def _detect(text: str) -> list[PIIMatch]:
    results = _analyzer().analyze(text=text, entities=_ENTITIES, language="en")
    # Highest-confidence, longest matches win; drop overlaps.
    ordered = sorted(results, key=lambda r: (-r.score, -(r.end - r.start), r.start))
    claimed: list[tuple[int, int]] = []
    matches: list[PIIMatch] = []
    for r in ordered:
        label = _ENTITY_MAP.get(r.entity_type)
        if label is None:
            continue
        if any(r.start < ce and cs < r.end for cs, ce in claimed):
            continue
        claimed.append((r.start, r.end))
        matches.append(PIIMatch(label, r.start, r.end))
    return matches


def redact(text: str) -> tuple[str, tuple[str, ...]]:
    return redact_matches(text, _detect(text))


def scan(text: str) -> tuple[str, ...]:
    return tuple(sorted({m.entity for m in _detect(text)}))
