"""Eval report structures + JSON serialization.

A run is an immutable snapshot, so the report is a plain nested structure that
maps 1:1 to a JSON document (see persistence.py for why JSON over sqlite).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class CaseReport:
    id: str
    tags: list[str]
    l1: dict[str, Any]
    l2: dict[str, Any]
    l3: dict[str, Any]
    # F4 additions (default-empty so older readers/builders stay valid).
    trajectory: dict[str, Any] = field(default_factory=dict)  # per-metric scores
    agent_judge: dict[str, Any] = field(default_factory=dict)  # trajectory verdict


@dataclass(frozen=True, slots=True)
class LevelAggregate:
    level: str
    mean_score: float
    passed: int
    scored: int  # number of cases to which the level applied


@dataclass(frozen=True, slots=True)
class Report:
    suite: str
    judge: str
    case_count: int
    created: int  # unix timestamp, stamped by the runner at runtime
    levels: dict[str, LevelAggregate]
    overall_score: float
    cases: list[CaseReport]
    # F4 suite-level additions (default-empty for back-compat).
    clear: dict[str, Any] = field(default_factory=dict)  # five CLEAR dimensions
    trajectory: dict[str, Any] = field(default_factory=dict)  # mean trajectory metrics

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
