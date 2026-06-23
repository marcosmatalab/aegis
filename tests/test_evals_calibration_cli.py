"""Tests for the `aegis calibrate` CLI (invoked in-process, offline)."""

from __future__ import annotations

import json

from aegis.cli import _calibrate_scope_line, main
from aegis.evals.calibration.kappa import ConfusionMatrix, KappaResult
from aegis.evals.calibration.report import KappaSection


def test_calibrate_mock_writes_report_and_summary(tmp_path, capsys):
    out = tmp_path / "calibration.json"
    rc = main(["calibrate", "--judge", "mock", "--output", str(out)])
    assert rc == 0
    assert out.exists()

    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["judge"] == "mock"
    assert report["threshold"] == 0.5
    assert report["n_cases"] == 30
    assert "n_parse_failed" in report
    assert set(report["per_criterion"]) == {"relevancy", "faithfulness"}
    matrix = report["global"]["confusion_matrix"]
    assert matrix["orientation"] == "rows=human, cols=judge; positive='pass'"

    captured = capsys.readouterr()
    # every scope line carries kappa, p_o, n_valid, parse_failed AND band together
    for scope in ("relevancy:", "faithfulness:", "global:"):
        assert scope in captured.out
    assert "kappa=" in captured.out and "p_o=" in captured.out and "band=" in captured.out
    # mock is flagged as a smoke test, not a real calibration
    assert "wiring smoke test" in captured.err


def test_calibrate_geval_without_key_exits_2(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rc = main(["calibrate", "--judge", "geval", "--output", str(tmp_path / "c.json")])
    assert rc == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_calibrate_bad_dataset_path_exits_2(tmp_path, capsys):
    rc = main(["calibrate", "--judge", "mock", "--dataset", str(tmp_path / "nope.jsonl")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_scope_line_renders_defined_and_undefined_stats():
    # a defined scope: kappa/p_o as fixed-precision numbers
    defined = KappaSection(
        result=KappaResult(0.5, 0.75, 0.5, 4, ConfusionMatrix(tp=2, tn=1, fp=1), "moderate"),
        n_cases=4,
        n_parse_failed=0,
    )
    line = _calibrate_scope_line("relevancy", defined)
    assert "kappa=0.500" in line and "p_o=0.750" in line and "band=moderate" in line

    # a degenerate scope: kappa/p_o render as 'undefined' (not 0.0, not a crash)
    degenerate = KappaSection(
        result=KappaResult(None, None, None, 0, ConfusionMatrix(), "undefined"),
        n_cases=2,
        n_parse_failed=2,
    )
    line = _calibrate_scope_line("faithfulness", degenerate)
    assert "kappa=undefined" in line and "p_o=undefined" in line
    assert "n_valid=0" in line and "parse_failed=2" in line and "band=undefined" in line
