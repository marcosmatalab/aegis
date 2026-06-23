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

    async def aclose(self) -> None:
        """Release any held resources (a provider's network client) on shutdown.

        No-op by default: the keyless ``MockJudge`` holds nothing, so it inherits
        this unchanged. Real judges override it; the runner calls it once when the
        suite finishes.
        """
        return None
