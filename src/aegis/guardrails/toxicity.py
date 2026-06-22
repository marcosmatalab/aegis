"""Basic, deterministic output toxicity detection (lexicon-based).

Explicitly *basic*: a small curated lexicon of threat/harassment patterns with
weights — NOT an ML classifier. The score is the summed weight of matched
patterns (capped at 1.0); the output is blocked when ``score >= threshold``.
Deterministic and offline. A real classifier (e.g. Llama Guard / Granite
Guardian) is a later-phase upgrade. Weights are tuned so a single mild insult
stays below the default 0.5 threshold while threats block on their own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_LEXICON: dict[str, float] = {
    r"\bkill yourself\b": 1.0,
    r"\bkys\b": 1.0,
    r"\bi(?:'| wi)ll kill you\b": 1.0,
    r"\bgo (?:and )?die\b": 1.0,
    r"\bi hate you\b": 0.6,
    r"\byou(?:'re| are) (?:an? )?(?:idiot|moron|loser|imbecile|scum)\b": 0.6,
    r"\bshut up\b": 0.4,
}
_COMPILED = [(re.compile(p, re.IGNORECASE), w) for p, w in _LEXICON.items()]


@dataclass(frozen=True, slots=True)
class ToxicityVerdict:
    hit: bool
    score: float
    terms: tuple[str, ...] = ()


def scan(text: str, *, threshold: float = 0.5) -> ToxicityVerdict:
    score = 0.0
    matched: list[str] = []
    for rx, weight in _COMPILED:
        if rx.search(text):
            score += weight
            matched.append(rx.pattern)
    score = min(1.0, score)
    hit = score > 0 and score >= threshold
    return ToxicityVerdict(hit=hit, score=score, terms=tuple(matched))
