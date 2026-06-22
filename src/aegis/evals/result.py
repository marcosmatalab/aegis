"""The shared result type returned by every eval scorer (L1/L2/L3)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Level = Literal["L1", "L2", "L3"]


@dataclass(frozen=True, slots=True)
class ScoreResult:
    """A single level's verdict for one case.

    ``score`` is in 0..1; ``passed`` is the strict per-level pass/fail used as the
    oracle in the golden set. ``reasons`` explains failures; ``breakdown`` carries
    structured detail (matched/missing items, sub-scores).
    """

    level: Level
    score: float
    passed: bool
    reasons: tuple[str, ...] = ()
    breakdown: dict[str, Any] = field(default_factory=dict)
