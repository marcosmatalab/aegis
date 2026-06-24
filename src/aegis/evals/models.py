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
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aegis.gateway.schemas import ChatMessage

_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ToolCall(BaseModel):
    """A single tool call: a flat name + already-parsed args (not the OpenAI
    nested ``{function: {arguments: json-string}}`` envelope), so L3 compares
    deterministically and golden lines stay human-authorable.

    ``status`` is the call OUTCOME (F4), defaulting to ``"ok"`` so it never
    affects L1/L3 (which compare only name+args) nor existing golden lines. The
    Agent-as-a-Judge uses it to detect error recovery (an ``"error"`` call later
    retried successfully)."""

    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    status: Literal["ok", "error"] = "ok"


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


class CaseTrace(BaseModel):
    """Optional per-case run telemetry for the CLEAR Cost/Latency dimensions.

    Every value field is optional because Aegis runs offline over a recorded golden
    set on the deterministic mock provider by default. Real telemetry arrives via the
    F1.x OTel bridge (``evals/telemetry_bridge``): a real provider span yields a
    real ``latency_ms`` and tokens, and ``cost_usd`` from the static price table.

    PROVENANCE is PER METRIC, because they differ honestly: latency from a real span
    is ``measured``; cost from real tokens x a STATIC list price is ``estimated``
    (not a true measurement); a hand-authored golden number is ``synthetic``. Both
    default to ``synthetic`` so every existing golden line stays synthetic with no
    edits. ``measured``/``estimated`` are LEGITIMATE ONLY when set programmatically by
    the runtime bridge — the dataset loader rejects them on hand-authored files (see
    :meth:`claims_real_telemetry`)."""

    model_config = ConfigDict(extra="forbid")
    latency_ms: float | None = Field(default=None, ge=0.0)
    cost_usd: float | None = Field(default=None, ge=0.0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    latency_source: Literal["measured", "synthetic"] = "synthetic"
    cost_source: Literal["estimated", "synthetic"] = "synthetic"

    def claims_real_telemetry(self) -> bool:
        """True if either provenance is non-synthetic — only valid via the runtime
        bridge, never from a hand-authored dataset line."""
        return self.latency_source != "synthetic" or self.cost_source != "synthetic"


class Milestone(BaseModel):
    """An AgentBoard-style subgoal checkpoint for Progress Rate (F4).

    A milestone is achieved ORDER-INDEPENDENTLY when either its ``tool`` was
    called or its ``output_contains`` phrase is present in the final output.
    Exactly one of the two must be set."""

    model_config = ConfigDict(extra="forbid")
    description: str = ""
    tool: str | None = None
    output_contains: str | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> Milestone:
        has_tool = bool(self.tool)
        has_output = bool(self.output_contains)
        if has_tool == has_output:
            raise ValueError("milestone must set exactly one of 'tool' or 'output_contains'")
        return self


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
    milestones: list[Milestone] = Field(default_factory=list)
    trace: CaseTrace | None = None
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
