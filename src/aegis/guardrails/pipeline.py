"""The guardrail pipeline: orchestrates input/output checks in defense-in-depth
order, gated by settings.

Ordering (cheapest first; a later, costlier check runs only if the earlier ones
pass): INPUT = injection -> policy -> PII redaction; OUTPUT = toxicity -> PII.
The PII engine is loaded lazily, so when the master switch is off or a cheaper
check blocks first, Presidio/spaCy are never imported.
"""

from __future__ import annotations

from fastapi import Depends

from aegis.gateway.config import Settings, get_settings
from aegis.gateway.schemas import ChatCompletionRequest
from aegis.guardrails import injection, policy, toxicity
from aegis.guardrails.content import flatten_content, map_content
from aegis.guardrails.pii_engine import PiiEngine, select_pii_engine
from aegis.guardrails.result import GuardrailResult

# Roles whose text is scanned for prompt injection (user/tool carry untrusted
# or retrieved content; indirect injection commonly arrives via tool results).
_INJECTION_ROLES = {"user", "tool"}


class GuardrailPipeline:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._pii_engine: PiiEngine | None = None

    def _pii(self) -> PiiEngine:
        if self._pii_engine is None:
            self._pii_engine = select_pii_engine(self.settings)
        return self._pii_engine

    @property
    def output_active(self) -> bool:
        """Whether any output check would run. When False, the proxy can stream
        with the original (non-buffering) generator for F1-identical behavior."""
        s = self.settings
        return s.guardrails_enabled and (s.gr_toxicity_enabled or s.gr_output_pii_enabled)

    async def check_input(self, request: ChatCompletionRequest) -> GuardrailResult:
        s = self.settings
        if not s.guardrails_enabled:
            return GuardrailResult.allow("input")

        checks: list[str] = []

        if s.gr_injection_enabled:
            checks.append("injection")
            for idx, msg in enumerate(request.messages):
                if msg.role in _INJECTION_ROLES:
                    verdict = injection.scan(flatten_content(msg.content))
                    if verdict.hit:
                        return GuardrailResult.block(
                            "input",
                            reason="Request blocked: possible prompt injection.",
                            code="prompt_injection",
                            param=f"messages[{idx}]",
                            checks_run=tuple(checks),
                        )

        if s.gr_policy_enabled and (s.gr_policy_deny or s.gr_policy_allow):
            checks.append("policy")
            for msg in request.messages:
                decision = policy.evaluate(
                    flatten_content(msg.content),
                    deny=s.gr_policy_deny,
                    allow=s.gr_policy_allow,
                )
                if decision.action == "deny":
                    return GuardrailResult.block(
                        "input",
                        reason="Request blocked by policy.",
                        code="policy_denied",
                        param=decision.rule_id,
                        checks_run=tuple(checks),
                    )

        if s.gr_pii_redact_input:
            checks.append("pii_redact")
            redacted, changed = self._redact_request(request)
            if changed:
                return GuardrailResult.allow(
                    "input", redacted_request=redacted, checks_run=tuple(checks)
                )

        return GuardrailResult.allow("input", checks_run=tuple(checks))

    async def check_output(self, text: str) -> GuardrailResult:
        s = self.settings
        if not s.guardrails_enabled:
            return GuardrailResult.allow("output")

        checks: list[str] = []

        if s.gr_toxicity_enabled:
            checks.append("toxicity")
            verdict = toxicity.scan(text, threshold=s.gr_toxicity_threshold)
            if verdict.hit:
                return GuardrailResult.block(
                    "output",
                    reason="Response blocked: toxic content.",
                    code="toxicity",
                    checks_run=tuple(checks),
                )

        if s.gr_output_pii_enabled:
            checks.append("pii_output")
            entities = self._pii().scan(text)
            if entities:
                if s.gr_output_pii_action == "redact":
                    redacted, _ = self._pii().redact(text)
                    return GuardrailResult.allow(
                        "output", redacted_text=redacted, checks_run=tuple(checks)
                    )
                return GuardrailResult.block(
                    "output",
                    reason="Response blocked: it would leak PII.",
                    code="pii_leak",
                    param=",".join(entities),
                    checks_run=tuple(checks),
                )

        return GuardrailResult.allow("output", checks_run=tuple(checks))

    def _redact_request(self, request: ChatCompletionRequest) -> tuple[ChatCompletionRequest, bool]:
        engine = self._pii()

        def _redact(text: str) -> str:
            return engine.redact(text)[0]

        new_messages = []
        changed = False
        for msg in request.messages:
            new_content = map_content(msg.content, _redact)
            if new_content != msg.content:
                changed = True
                new_messages.append(msg.model_copy(update={"content": new_content}))
            else:
                new_messages.append(msg)
        if not changed:
            return request, False
        return request.model_copy(update={"messages": new_messages}), True


def build_pipeline(settings: Settings) -> GuardrailPipeline:
    return GuardrailPipeline(settings)


def get_guardrail_pipeline(settings: Settings = Depends(get_settings)) -> GuardrailPipeline:
    """FastAPI dependency returning the active pipeline (overridable in tests)."""
    return build_pipeline(settings)
