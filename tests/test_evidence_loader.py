"""Loader: missing-default => None, missing-explicit/corrupt => error; JSON sidecar
round-trips and preserves true Unicode (the em-dash the PDF will transliterate)."""

from __future__ import annotations

import json

import pytest

from aegis.evidence.builder import build_evidence
from aegis.evidence.loader import EvidenceInputError, read_report
from aegis.evidence.persistence import write_evidence_json
from aegis.gateway.config import Settings


def test_missing_default_path_is_none(tmp_path):
    assert read_report(tmp_path / "absent-evidence.json", required=False) is None


def test_missing_explicit_path_is_an_error(tmp_path):
    with pytest.raises(EvidenceInputError, match="report not found"):
        read_report(tmp_path / "nope.json", required=True)


def test_present_valid_report_loads(tmp_path):
    p = tmp_path / "eval.json"
    p.write_text(json.dumps({"suite": "golden", "judge": "mock"}), encoding="utf-8")
    data = read_report(p)
    assert data["suite"] == "golden"


def test_present_but_corrupt_report_is_an_error(tmp_path):
    p = tmp_path / "eval.json"
    p.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(EvidenceInputError, match="unreadable/corrupt"):
        read_report(p)


def test_present_but_non_object_report_is_an_error(tmp_path):
    p = tmp_path / "eval.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(EvidenceInputError, match="not a JSON object"):
        read_report(p)


def test_sidecar_round_trips_and_preserves_unicode(tmp_path):
    rep = build_evidence(
        eval_report=None,
        redteam_report=None,
        calibration_report={
            "judge": "geval",
            "global": {"kappa": 0.933, "band": "almost perfect", "n_valid": 30, "p_o": 0.96},
        },
        settings=Settings(_env_file=None),
    )
    out = write_evidence_json(rep, tmp_path / "evidence.json")
    raw = out.read_text(encoding="utf-8")
    data = json.loads(raw)
    assert data["disclaimer"].startswith("This document is PARTIAL TECHNICAL EVIDENCE")
    assert "summary_counts" in data and "controls" in data
    # the JSON keeps true Unicode (ensure_ascii=False): the em-dash artifact_source on
    # out-of-scope rows survives verbatim — the PDF renderer is the only thing that
    # transliterates it to latin-1.
    assert "—" in raw  # em-dash
    cal = next(c for c in data["controls"] if c["control_id"] == "MEASURE 2.13")
    assert "kappa=0.933" in cal["derived_value"]
