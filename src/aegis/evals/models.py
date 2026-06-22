"""Pydantic v2 models for F3 eval cases (the golden dataset rows).

An ``EvalCase`` is self-contained and scoreable OFFLINE at all three levels: it
carries the L1 inputs (``user_goal``, ``success_criteria``), the L3 inputs
(``expected_trajectory`` vs ``actual.tool_calls``), the L2 inputs
(``reference_answer`` + ``context`` vs ``actual.final_output``), and an
``expected`` oracle recording the intended verdict per level so each golden line
is its own assertion. ``extra="forbid"`` on these models catches typos in
hand-authored golden lines.
"""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis.gateway.schemas import ChatMessage

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ToolCall(BaseModel):
    """A single tool call: a flat name + already-parsed args (not the OpenAI
    nested ``{function: {arguments: json-string}}`` envelope), so L3 compares
    deterministically and golden lines stay human-authorable."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class CandidateOutput(BaseModel):
    """What the system-under-test produced for this case (recorded, not live)."""

    model_config = ConfigDict(extra="forbid")
    final_output: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)


class SuccessCriteria(BaseModel):
    """Deterministic L1 goal criteria: required and forbidden substrings
    (matched as whole words by the L1 scorer)."""

    model_config = ConfigDict(extra="forbid")
    must_include: list[str] = Field(default_factory=list)
    must_not_include: list[str] = Field(default_factory=list)


class ExpectedVerdict(BaseModel):
    """The per-level oracle for a case. ``l2_faithful=None`` means the case has
    no L2 reference/context, so L2 does not apply (excluded from aggregates)."""

    model_config = ConfigDict(extra="forbid")
    l1_goal_met: bool
    l2_faithful: bool | None = None
    l3_trajectory_match: bool


class EvalCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    user_goal: str
    input_messages: list[ChatMessage] = Field(min_length=1)
    expected_trajectory: list[ToolCall] = Field(default_factory=list)
    reference_answer: str | None = None
    context: list[str] = Field(default_factory=list)
    success_criteria: SuccessCriteria = Field(default_factory=SuccessCriteria)
    actual: CandidateOutput
    expected: ExpectedVerdict
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate(self) -> EvalCase:
        if not _ID_RE.match(self.id):
            raise ValueError(f"case id must be slug-shaped ([a-z0-9-]), got {self.id!r}")
        if self.expected.l2_faithful is not None and not (self.reference_answer or self.context):
            raise ValueError(
                "expected.l2_faithful is set but there is no reference_answer/context to judge"
            )
        return self
