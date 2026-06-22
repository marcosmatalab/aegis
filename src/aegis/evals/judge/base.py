"""The Judge interface for L2 response-quality scoring.

Mirrors F1's Provider ABC: an abstract async ``score`` returning a frozen
verdict. The judge is treated as DIRECTIONAL — a signal to validate against human
labels (a later phase), never ground truth.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class JudgeVerdict:
    score: float  # 0..1
    reasoning: str
    criteria: str = ""
    judge: str = ""


class Judge(ABC):
    name: str

    @abstractmethod
    async def score(
        self,
        criteria: str,
        output: str,
        *,
        reference: str | None = None,
        context: list[str] | None = None,
    ) -> JudgeVerdict: ...
