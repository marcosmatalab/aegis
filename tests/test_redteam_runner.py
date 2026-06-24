"""run_redteam over the committed catalog — offline, hermetic, self-consistent."""

from __future__ import annotations

import json

import pytest

from aegis.evals.persistence import write_redteam_report
from aegis.redteam.dataset import load_attacks
from aegis.redteam.runner import build_redteam_settings, run_redteam


def test_self_consistency_oracle_and_honest_rate():
    # the LOCK: every committed row's authored expected_outcome+code must equal what
    # the REAL pipeline produces, so the catalog can never drift from behaviour.
    report = run_redteam(load_attacks(), created=0)
    assert report.overall_oracle_match_rate == 1.0
    assert report.findings == []  # self-consistent: no attack_passed / oracle_mismatch
    # honest coverage: genuinely below 100% because named gaps slip through
    assert report.overall_detection_rate < 1.0
    assert report.case_count == 25
    assert report.known_gaps  # the gaps are surfaced, not hidden


def test_per_category_detection_and_policy_really_denies():
    report = run_redteam(load_attacks())
    cats = report.categories
    assert set(cats) >= {"prompt_injection", "pii_input", "output_toxicity", "policy_denylist"}
    # the regex injection category has real misses (leetspeak + 3 non-scanned roles)
    assert cats["prompt_injection"].detection_rate < 1.0
    # the bundled deny-list is NOT inert: policy attacks block with code=policy_denied
    pol = cats["policy_denylist"]
    assert pol.blocked == pol.total and pol.by_code == {"policy_denied": pol.total}


def test_run_is_hermetic_and_ignores_hostile_env(monkeypatch):
    # every AEGIS_GR_* toggle pointed at a behaviour-FLIPPING value (a 0.01 toxicity
    # threshold would block "shut up"; disabling injection/PII would drop many
    # blocks). build_redteam_settings pins them all, so nothing changes.
    monkeypatch.setenv("AEGIS_GUARDRAILS_ENABLED", "false")
    monkeypatch.setenv("AEGIS_GR_PII_ENGINE", "presidio")
    monkeypatch.setenv("AEGIS_GR_TOXICITY_THRESHOLD", "0.01")
    monkeypatch.setenv("AEGIS_GR_INJECTION_ENABLED", "false")
    monkeypatch.setenv("AEGIS_GR_PII_REDACT_INPUT", "false")
    monkeypatch.setenv("AEGIS_GR_OUTPUT_PII_ENABLED", "false")
    monkeypatch.setenv("AEGIS_GR_TOXICITY_ENABLED", "false")

    # the constructed settings ignore the env entirely (init kwargs win)
    s = build_redteam_settings()
    assert s.guardrails_enabled is True and s.gr_pii_engine == "regex"
    assert s.gr_toxicity_threshold == 0.5 and s.gr_injection_enabled is True
    assert s.gr_pii_redact_input is True and s.gr_output_pii_enabled is True
    assert s.gr_toxicity_enabled is True

    # and the full run still reproduces the oracle exactly
    report = run_redteam(load_attacks())
    assert report.overall_oracle_match_rate == 1.0
    assert report.findings == []


def test_report_to_dict_persists(tmp_path):
    report = run_redteam(load_attacks(), suite="rt", created=42)
    out = write_redteam_report(report, tmp_path / "rt.json")
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["suite"] == "rt" and data["created"] == 42 and data["case_count"] == 25
    assert "categories" in data and "overall" in data and "known_gaps" in data
    pi = data["categories"]["prompt_injection"]
    assert pi["owasp"] == "LLM01" and "detection_rate" in pi
    assert data["categories"]["output_toxicity"]["owasp"] is None  # no clean slot
    assert data["findings"] == []  # healthy run


@pytest.mark.parametrize("cat,owasp", [("system_prompt_leak", "LLM07"), ("pii_output", "LLM02")])
def test_category_owasp_mapping_in_report(cat, owasp):
    report = run_redteam(load_attacks())
    assert report.categories[cat].owasp == owasp
