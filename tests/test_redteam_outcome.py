"""classify_result + AttackResult — offline, hand-built GuardrailResults."""

from __future__ import annotations

from aegis.gateway.schemas import ChatCompletionRequest
from aegis.guardrails.result import GuardrailResult
from aegis.redteam.models import AttackCase
from aegis.redteam.outcome import AttackResult, classify_result

_REQ = ChatCompletionRequest(model="mock/echo-1", messages=[{"role": "user", "content": "x"}])


def test_classify_blocked_input():
    r = GuardrailResult.block("input", reason="x", code="prompt_injection", param="messages[0]")
    assert classify_result(r) == ("blocked", "prompt_injection")


def test_classify_redacted_input():
    r = GuardrailResult.allow("input", redacted_request=_REQ)
    assert classify_result(r) == ("redacted", None)


def test_classify_passed_input():
    assert classify_result(GuardrailResult.allow("input")) == ("passed", None)


def test_classify_blocked_output():
    r = GuardrailResult.block("output", reason="x", code="toxicity")
    assert classify_result(r) == ("blocked", "toxicity")


def test_classify_redacted_output():
    r = GuardrailResult.allow("output", redacted_text="redacted")
    assert classify_result(r) == ("redacted", None)


def test_classify_passed_output():
    assert classify_result(GuardrailResult.allow("output")) == ("passed", None)


def _case(**over) -> AttackCase:
    row = {
        "id": "inj-01",
        "vector": "input",
        "category": "prompt_injection",
        "payload": "p",
        "expected_outcome": "blocked",
        "expected_code": "prompt_injection",
    }
    row.update(over)
    return AttackCase.model_validate(row)


def test_attack_result_detected_and_oracle():
    blocked = AttackResult(_case(), "blocked", "prompt_injection")
    assert blocked.detected is True and blocked.matches_oracle is True

    wrong_code = AttackResult(_case(), "blocked", "policy_denied")
    assert wrong_code.detected is True and wrong_code.matches_oracle is False

    passed = AttackResult(_case(), "passed", None)
    assert passed.detected is False and passed.matches_oracle is False
