"""Pydantic model for a hand-labeled judge-calibration row.

A ``CalibrationCase`` is one rubric judgment a SINGLE annotator made by hand:
the text to judge, the grounding (a ``reference`` for relevancy, a ``context``
for faithfulness), and the categorical ``human_label`` (pass/fail).

``human_label`` is the SOLE driver of Cohen's kappa. ``human_score`` (0.0/1.0)
is a redundant numeric mirror kept only to cross-check the label at load time —
it is never averaged into the agreement math. ``extra="forbid"`` catches typos
in the hand-authored lines.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class CalibrationCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    criterion_type: Literal["relevancy", "faithfulness"]
    criterion: str = Field(min_length=1)
    output: str
    reference: str | None = None
    context: list[str] | None = None
    human_label: Literal["pass", "fail"]
    human_score: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate(self) -> CalibrationCase:
        if not _ID_RE.match(self.id):
            raise ValueError(f"case id must be slug-shaped ([a-z0-9-]), got {self.id!r}")

        # Relevancy is judged against a reference; faithfulness against a context.
        # Each row must carry exactly its own grounding and not the other's.
        if self.criterion_type == "relevancy":
            if not self.reference:
                raise ValueError("relevancy case requires a non-empty 'reference'")
            if self.context:
                raise ValueError("relevancy case must not carry 'context'")
        else:  # faithfulness
            if not self.context:
                raise ValueError("faithfulness case requires a non-empty 'context'")
            if self.reference:
                raise ValueError("faithfulness case must not carry 'reference'")

        # human_score is a redundant cross-check of human_label, never the kappa
        # driver: pass <-> 1.0, fail <-> 0.0. A mismatch (or any other value) is a
        # hand-label typo and fails loudly at load.
        expected = 1.0 if self.human_label == "pass" else 0.0
        if self.human_score != expected:
            raise ValueError(
                f"human_score {self.human_score} is inconsistent with human_label "
                f"{self.human_label!r} (expected {expected})"
            )
        return self
