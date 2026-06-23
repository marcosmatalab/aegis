"""redteam_findings — pure, observed-vs-oracle logic (the F7-additive seam)."""

from __future__ import annotations

from aegis.evals.baseline import Regression
from aegis.redteam.findings import RedteamFinding, redteam_findings
from aegis.redteam.models import AttackCase
from aegis.redteam.outcome import AttackResult


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


def _gap() -> AttackCase:
    return _case(
        id="inj-gap",
        expected_outcome="passed",
        expected_code=None,
        is_known_gap=True,
        gap_reason="leetspeak",
    )


def test_unexpected_pass_is_attack_passed_finding():
    fs = redteam_findings([AttackResult(_case(), "passed", None)])
    assert [f.kind for f in fs] == ["attack_passed"]
    assert "inj-01 prompt_injection" in str(fs[0])


def test_oracle_match_produces_no_finding():
    assert redteam_findings([AttackResult(_case(), "blocked", "prompt_injection")]) == []


def test_known_gap_pass_is_not_a_finding():
    # a documented gap expects 'passed', so observing 'passed' matches the oracle
    assert redteam_findings([AttackResult(_gap(), "passed", None)]) == []


def test_wrong_outcome_is_oracle_mismatch():
    fs = redteam_findings([AttackResult(_case(), "redacted", None)])  # expected blocked
    assert [f.kind for f in fs] == ["oracle_mismatch"]


def test_wrong_code_is_oracle_mismatch():
    fs = redteam_findings([AttackResult(_case(), "blocked", "policy_denied")])
    assert [f.kind for f in fs] == ["oracle_mismatch"]


def test_gap_now_blocked_is_oracle_mismatch():
    # a previously-passing gap that now blocks (regex improved) is benign drift
    fs = redteam_findings([AttackResult(_gap(), "blocked", "prompt_injection")])
    assert [f.kind for f in fs] == ["oracle_mismatch"]


def test_empty_results():
    assert redteam_findings([]) == []


def test_finding_shape_matches_baseline_regression():
    # the F7-additive contract: same fields + same __str__ so a future gate unions them
    f = RedteamFinding("attack_passed", "inj-01 prompt_injection", "slipped")
    r = Regression("attack_passed", "inj-01 prompt_injection", "slipped")
    assert str(f) == str(r)
    assert {*RedteamFinding.__dataclass_fields__} == {*Regression.__dataclass_fields__}
