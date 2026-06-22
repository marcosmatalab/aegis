"""Tests for the `aegis eval run` CLI (invoked in-process, offline)."""

from __future__ import annotations

import json

from aegis.cli import main


def test_eval_run_writes_report_and_summary(tmp_path, capsys):
    out = tmp_path / "report.json"
    rc = main(["eval", "run", "--suite", "t", "--output", str(out)])
    assert rc == 0
    assert out.exists()
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["suite"] == "t"
    assert set(report["levels"]) == {"L1", "L2", "L3"}
    summary = capsys.readouterr().out
    assert "overall=" in summary
    assert "L1:" in summary


def test_fail_under_seam_is_inert_by_default(tmp_path):
    # no --fail-under -> always exit 0 regardless of score (gate is F7)
    out = tmp_path / "r.json"
    assert main(["eval", "run", "--output", str(out)]) == 0


def test_fail_under_blocks_when_explicit_and_below(tmp_path):
    # overall <= 1.0, so a threshold above 1 forces the gate to trip
    out = tmp_path / "r.json"
    rc = main(["eval", "run", "--output", str(out), "--fail-under", "1.01"])
    assert rc == 1


def test_geval_backend_fails_cleanly(tmp_path, capsys):
    out = tmp_path / "r.json"
    rc = main(["eval", "run", "--judge", "geval", "--output", str(out)])
    assert rc == 2
    assert "not wired in F3" in capsys.readouterr().err


def test_bad_dataset_path_fails_cleanly(tmp_path, capsys):
    rc = main(["eval", "run", "--dataset", str(tmp_path / "nope.jsonl")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err
