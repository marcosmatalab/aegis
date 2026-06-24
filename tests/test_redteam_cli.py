"""Tests for `aegis redteam run` (invoked in-process, offline)."""

from __future__ import annotations

import json

from aegis.cli import main


def test_redteam_run_writes_report_and_summary(tmp_path, capsys):
    out = tmp_path / "rt.json"
    rc = main(["redteam", "run", "--output", str(out)])
    assert rc == 0
    assert out.exists()

    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["case_count"] == 25
    assert set(report["categories"]) >= {"prompt_injection", "pii_input", "policy_denylist"}

    summary = capsys.readouterr().out
    assert "prompt_injection (LLM01)" in summary
    assert "overall: detected=" in summary
    assert "known gaps (passed by design)" in summary  # passing attacks surfaced


def test_redteam_fail_under_detection_floor(tmp_path, capsys):
    out = tmp_path / "rt.json"
    # the real overall rate is ~0.72; a 0.90 floor must trip exit 1
    rc = main(["redteam", "run", "--output", str(out), "--fail-under-detection", "0.90"])
    assert rc == 1
    assert "FAIL: detection" in capsys.readouterr().err


def test_redteam_fail_under_detection_passes_below_floor(tmp_path):
    out = tmp_path / "rt.json"
    assert main(["redteam", "run", "--output", str(out), "--fail-under-detection", "0.50"]) == 0


def test_redteam_bad_dataset_exits_2(tmp_path, capsys):
    rc = main(["redteam", "run", "--dataset", str(tmp_path / "nope.jsonl")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err
