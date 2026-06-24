"""Tests for the `aegis eval run` CLI (invoked in-process, offline)."""

from __future__ import annotations

import json

from aegis.cli import _format_clear, main


def _dim(name, status, *, score=None, value=None, unit="usd", applicable=True):
    return {
        "name": name,
        "status": status,
        "applicable": applicable,
        "score": score,
        "value": value,
        "unit": unit,
        "basis": "",
    }


def test_format_clear_marks_non_measured_and_keeps_measured_clean():
    # measured renders WITHOUT a suffix on both the scored and raw-value paths
    assert _format_clear(_dim("latency", "measured", value=120.0, unit="ms")) == "latency=120ms"
    assert _format_clear(_dim("accuracy", "measured", score=0.9, unit="ratio")) == "accuracy=0.900"
    # estimated / synthetic / placeholder always carry the honest suffix
    assert _format_clear(_dim("cost", "estimated", value=0.012)) == "cost=0.012usd(estimated)"
    assert _format_clear(_dim("cost", "synthetic", value=0.03)) == "cost=0.03usd(synthetic)"
    ph = _format_clear(_dim("cost", "placeholder", value=None, applicable=False))
    assert ph == "cost=n/a(placeholder)"


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


def test_fail_under_boundary_equal_passes(tmp_path):
    # overall exactly 1.0 with --fail-under 1.0: strict `<` means it passes (rc 0)
    case = {
        "id": "a",
        "user_goal": "g",
        "input_messages": [{"role": "user", "content": "hi"}],
        "expected_trajectory": [],
        "success_criteria": {"must_include": ["ok"]},
        "actual": {"final_output": "ok", "tool_calls": []},
        "expected": {"l1_goal_met": True, "l2_faithful": None, "l3_trajectory_match": True},
    }
    ds = tmp_path / "g.jsonl"
    ds.write_text(json.dumps(case), encoding="utf-8")
    out = tmp_path / "r.json"
    rc = main(["eval", "run", "--dataset", str(ds), "--output", str(out), "--fail-under", "1.0"])
    assert rc == 0


def test_summary_includes_clear_and_trajectory_lines(tmp_path, capsys):
    out = tmp_path / "r.json"
    assert main(["eval", "run", "--output", str(out)]) == 0
    summary = capsys.readouterr().out
    assert "trajectory:" in summary
    assert "CLEAR:" in summary
    assert "accuracy=" in summary
    # the golden carries a synthetic trace case -> cost/latency are flagged synthetic
    assert "(synthetic)" in summary


def test_clear_placeholder_when_dataset_has_no_trace(tmp_path, capsys):
    case = {
        "id": "no-trace",
        "user_goal": "g",
        "input_messages": [{"role": "user", "content": "hi"}],
        "expected_trajectory": [],
        "success_criteria": {"must_include": ["ok"]},
        "actual": {"final_output": "ok", "tool_calls": []},
        "expected": {"l1_goal_met": True, "l2_faithful": None, "l3_trajectory_match": True},
    }
    ds = tmp_path / "g.jsonl"
    ds.write_text(json.dumps(case), encoding="utf-8")
    main(["eval", "run", "--dataset", str(ds), "--output", str(tmp_path / "r.json")])
    assert "cost=n/a(placeholder)" in capsys.readouterr().out


def test_report_json_has_clear_and_per_case_f4_fields(tmp_path):
    out = tmp_path / "r.json"
    main(["eval", "run", "--output", str(out)])
    report = json.loads(out.read_text(encoding="utf-8"))
    assert set(report["clear"]) == {"cost", "latency", "efficiency", "accuracy", "reliability"}
    assert report["clear"]["accuracy"]["status"] == "measured"
    first = report["cases"][0]
    assert set(first["trajectory"]) == {
        "tool_correctness",
        "trajectory_accuracy",
        "progress_rate",
        "t_eval",
    }
    assert "has_loop" in first["agent_judge"]


def test_geval_backend_fails_cleanly(tmp_path, capsys, monkeypatch):
    # geval with no key/SDK -> the provider can't be built -> clean exit 2 offline
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = tmp_path / "r.json"
    rc = main(["eval", "run", "--judge", "geval", "--output", str(out)])
    assert rc == 2
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err


def test_bad_dataset_path_fails_cleanly(tmp_path, capsys):
    rc = main(["eval", "run", "--dataset", str(tmp_path / "nope.jsonl")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err
