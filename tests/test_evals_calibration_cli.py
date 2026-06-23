"""Tests for the `aegis calibrate` CLI (invoked in-process, offline)."""

from __future__ import annotations

import json

from aegis.cli import main


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
