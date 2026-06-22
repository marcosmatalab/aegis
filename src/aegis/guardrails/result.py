"""The ``GuardrailResult`` value object returned by the guardrail pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from aegis.gateway.schemas import ChatCompletionRequest

Stage = Literal["input", "output"]


@dataclass(frozen=True, slots=True)
class GuardrailResult:
    """Outcome of a guardrail stage.

    On allow, ``redacted_request`` (input) / ``redacted_text`` (output) may carry
    a sanitized payload to use instead of the original; ``None`` means "use the
    original unchanged". On block, ``reason``/``code``/``param`` describe why.
    ``checks_run`` records which checks executed (audit trail for a later phase).
    """

    blocked: bool
    stage: Stage
    reason: str | None = None
    type: str = "guardrail_blocked"
    code: str | None = None
    param: str | None = None
    redacted_request: ChatCompletionRequest | None = None
    redacted_text: str | None = None
    checks_run: tuple[str, ...] = ()

    @classmethod
    def allow(
        cls,
        stage: Stage,
        *,
        redacted_request: ChatCompletionRequest | None = None,
        redacted_text: str | None = None,
        checks_run: tuple[str, ...] = (),
    ) -> GuardrailResult:
        return cls(
            blocked=False,
            stage=stage,
            redacted_request=redacted_request,
            redacted_text=redacted_text,
            checks_run=tuple(checks_run),
        )

    @classmethod
    def block(
        cls,
        stage: Stage,
        *,
        reason: str,
        code: str,
        param: str | None = None,
        checks_run: tuple[str, ...] = (),
    ) -> GuardrailResult:
        return cls(
            blocked=True,
            stage=stage,
            reason=reason,
            code=code,
            param=param,
            checks_run=tuple(checks_run),
        )
