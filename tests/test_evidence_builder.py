"""Pure build_evidence: status is DERIVED from real artifact fields, with the honesty
gates (mock cap, kappa-null, guardrails-off, synthetic CLEAR). No fpdf2, no I/O."""

from __future__ import annotations

from aegis.evidence.builder import build_evidence
from aegis.gateway.config import Settings


def _eval(judge="geval"):
    return {
        "suite": "golden",
        "judge": judge,
        "case_count": 32,
        "created": 0,
        "levels": {
            "L1": {"mean_score": 0.85, "passed": 25, "scored": 32},
            "L2": {"mean_score": 0.86, "passed": 13, "scored": 15},
            "L3": {"mean_score": 0.87, "passed": 22, "scored": 32},
        },
        "overall_score": 0.86,
        "clear": {
            "accuracy": {
                "name": "accuracy",
                "status": "measured",
                "value": 0.86,
                "applicable": True,
            },
            "reliability": {
                "name": "reliability",
                "status": "measured",
                "value": 0.78,
                "applicable": True,
            },
            "efficiency": {
                "name": "efficiency",
                "status": "measured",
                "value": 0.9,
                "applicable": True,
            },
            "cost": {"name": "cost", "status": "placeholder", "value": None},
            "latency": {"name": "latency", "status": "placeholder", "value": None},
        },
    }


def _redteam():
    return {
        "suite": "redteam",
        "created": 0,
        "case_count": 25,
        "categories": {
            "prompt_injection": {"owasp": "LLM01", "detection_rate": 0.636},
            "output_toxicity": {"owasp": None, "detection_rate": 0.5},
            "pii_output": {"owasp": "LLM02", "detection_rate": 0.667},
        },
        "overall": {"detection_rate": 0.72, "oracle_match_rate": 1.0},
        "known_gaps": [
            {"id": "leetspeak-override", "category": "prompt_injection", "owasp": "LLM01"}
        ],
        "findings": [],
    }


def _calib(judge="geval", kappa=0.933, band="almost perfect", n_valid=30):
    return {
        "judge": judge,
        "threshold": 0.5,
        "created": 0,
        "n_cases": 30,
        "n_parse_failed": 0,
        "global": {"kappa": kappa, "p_o": 0.967, "p_e": 0.5, "n_valid": n_valid, "band": band},
        "per_criterion": {},
    }


def _control(report, framework_substr, control_id):
    return next(
        c
        for c in report.controls
        if c.framework.startswith(framework_substr) and c.control_id == control_id
    )


def _settings(**kw):
    return Settings(_env_file=None, **kw)


def test_all_artifacts_absent_yields_not_covered_and_out_of_scope_only():
    rep = build_evidence(
        eval_report=None,
        redteam_report=None,
        calibration_report=None,
        settings=_settings(guardrails_enabled=False, otel_enabled=False),
    )
    assert rep.summary_counts["covered"] == 0
    assert rep.summary_counts["partial"] == 0
    assert rep.summary_counts["not_covered"] > 0 and rep.summary_counts["out_of_scope"] > 0
    assert rep.inputs_present == {
        "eval": False,
        "redteam": False,
        "calibration": False,
        "settings": True,
    }
    # an absent artifact shows the produce-it command, never a fabricated value
    acc = _control(rep, "EU AI Act", "Article 15(1)/(3)")
    assert acc.status == "not_covered" and "aegis eval run" in acc.derived_value


def test_real_judge_eval_is_covered_redteam_and_posture_too():
    rep = build_evidence(
        eval_report=_eval("geval"),
        redteam_report=_redteam(),
        calibration_report=_calib("geval"),
        settings=_settings(guardrails_enabled=True, gr_policy_deny=["a", "b"], otel_enabled=True),
    )
    assert _control(rep, "EU AI Act", "Article 15(1)/(3)").status == "covered"
    assert _control(rep, "NIST", "MEASURE 2.5").status == "covered"
    rob = _control(rep, "EU AI Act", "Article 15(4)")
    assert (
        rob.status == "covered"
        and "named gaps" in rob.derived_value
        and "directional" in rob.caveat
    )
    assert _control(rep, "NIST", "MEASURE 2.6").status == "partial"  # safety only partial
    cal = _control(rep, "NIST", "MEASURE 2.13")
    assert cal.status == "covered" and "kappa=0.933" in cal.derived_value
    posture = _control(rep, "EU AI Act", "Article 15(5)")
    assert posture.status == "covered" and "deny=2" in posture.derived_value
    assert "generation time" in posture.caveat  # posture != red-team run config
    assert _control(rep, "ISO/IEC 42001", "A.6.2.8").status == "covered"  # otel on


def test_mock_judge_caps_eval_controls_at_partial():
    rep = build_evidence(
        eval_report=_eval("mock"),
        redteam_report=None,
        calibration_report=None,
        settings=_settings(guardrails_enabled=True),
    )
    acc = _control(rep, "EU AI Act", "Article 15(1)/(3)")
    assert acc.status == "partial" and "judge=mock" in acc.caveat
    assert _control(rep, "NIST", "MEASURE 2.3").status == "partial"
    assert _control(rep, "ISO/IEC 42001", "A.6.2.4").status == "partial"


def test_calibration_kappa_undefined_is_not_covered_never_covered():
    rep = build_evidence(
        eval_report=None,
        redteam_report=None,
        calibration_report=_calib("geval", kappa=None, band="undefined", n_valid=0),
        settings=_settings(),
    )
    cal = _control(rep, "NIST", "MEASURE 2.13")
    assert cal.status == "not_covered" and "undefined" in cal.derived_value


def test_mock_calibration_is_partial_not_covered():
    rep = build_evidence(
        eval_report=None,
        redteam_report=None,
        calibration_report=_calib("mock"),
        settings=_settings(),
    )
    assert _control(rep, "NIST", "MEASURE 2.13").status == "partial"


def test_guardrails_off_renders_posture_not_covered_honestly():
    rep = build_evidence(
        eval_report=None,
        redteam_report=None,
        calibration_report=None,
        settings=_settings(guardrails_enabled=False, otel_enabled=False),
    )
    posture = _control(rep, "EU AI Act", "Article 15(5)")
    assert posture.status == "not_covered" and "disabled" in posture.derived_value
    assert _control(rep, "ISO/IEC 42001", "A.6.2.8").status == "not_covered"  # otel off


def test_no_control_is_covered_without_a_real_artifact():
    # the crux: every covered/partial control names a real artifact_source, never "—"
    rep = build_evidence(
        eval_report=_eval("geval"),
        redteam_report=_redteam(),
        calibration_report=_calib("geval"),
        settings=_settings(guardrails_enabled=True, otel_enabled=True),
    )
    for c in rep.controls:
        if c.status in ("covered", "partial"):
            assert c.artifact_source != "—", c
            assert c.fields_read, c
