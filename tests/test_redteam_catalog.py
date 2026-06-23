"""The committed attack catalog is well-formed (static checks; the pipeline
self-consistency oracle is asserted in the runner's test)."""

from __future__ import annotations

from aegis.redteam.dataset import load_attacks

_CATEGORIES = {
    "prompt_injection",
    "system_prompt_leak",
    "pii_input",
    "pii_output",
    "output_toxicity",
    "policy_denylist",
}


def test_catalog_loads_and_is_well_formed():
    cases = load_attacks()
    assert len(cases) == 25
    assert len({c.id for c in cases}) == 25
    assert {c.category for c in cases} == _CATEGORIES

    # derived OWASP-2025 mapping is honest (None where there is no clean slot)
    owasp = {c.category: c.owasp for c in cases}
    assert owasp["prompt_injection"] == "LLM01"
    assert owasp["system_prompt_leak"] == "LLM07"
    assert owasp["pii_input"] == "LLM02" and owasp["pii_output"] == "LLM02"
    assert owasp["output_toxicity"] is None and owasp["policy_denylist"] is None


def test_catalog_has_honest_named_gaps():
    cases = load_attacks()
    gaps = [c for c in cases if c.is_known_gap]
    assert len(gaps) >= 5  # the rate is genuinely <100%
    assert all(c.expected_outcome == "passed" and c.gap_reason for c in gaps)
    # every passed row is a flagged gap and vice-versa (no silent green)
    assert all((c.expected_outcome == "passed") == c.is_known_gap for c in cases)


def test_catalog_discloses_role_blindspot_and_leak_overlap():
    cases = load_attacks()
    gap_roles = {c.role for c in cases if "role-gap" in c.tags}
    assert {"system", "assistant", "developer"} <= gap_roles
    leaks = [c for c in cases if c.category == "system_prompt_leak"]
    assert leaks and all("LLM01" in c.overlap for c in leaks)
