"""CLI tests for `aegis eval gate` — invoked in-process, fully offline.

Uses tmp baselines (the committed golden baseline is added in its own commit), so
these exercise the command surface, exit codes, and the offline-by-construction
guarantee without depending on the shipped contract.
"""

from __future__ import annotations

import json

from aegis.cli import main


def _make_baseline(tmp_path):
    bl = tmp_path / "b.json"
    assert main(["eval", "gate", "--baseline", str(bl), "--update-baseline"]) == 0
    return bl


def test_update_baseline_then_gate_passes(tmp_path, capsys):
    bl = _make_baseline(tmp_path)
    assert bl.exists()
    capsys.readouterr()
    rc = main(["eval", "gate", "--baseline", str(bl)])
    assert rc == 0
    assert "PASS" in capsys.readouterr().out


def test_gate_fails_on_regression_naming_scope(tmp_path, capsys):
    bl = _make_baseline(tmp_path)
    data = json.loads(bl.read_text(encoding="utf-8"))
    # tamper the baseline to expect a HIGHER L1 mean -> the fresh run looks like a drop
    data["levels"]["L1"]["mean_score"] = min(1.0, data["levels"]["L1"]["mean_score"] + 0.5)
    bl.write_text(json.dumps(data), encoding="utf-8")
    capsys.readouterr()

    rc = main(["eval", "gate", "--baseline", str(bl)])
    err = capsys.readouterr().err
    assert rc == 1
    assert "FAIL" in err and "L1" in err


def test_missing_baseline_exits_2(tmp_path, capsys):
    rc = main(["eval", "gate", "--baseline", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_id_set_drift_exits_2(tmp_path, capsys):
    bl = _make_baseline(tmp_path)
    data = json.loads(bl.read_text(encoding="utf-8"))
    data["cases"].pop(next(iter(data["cases"])))  # baseline now misses a case -> drift
    bl.write_text(json.dumps(data), encoding="utf-8")
    capsys.readouterr()

    rc = main(["eval", "gate", "--baseline", str(bl)])
    assert rc == 2
    assert "case-set changed" in capsys.readouterr().err


def test_gate_is_offline_by_construction(tmp_path, monkeypatch):
    # even with both judge backends pointed at the real (networked) judges and NO
    # key, the gate forces the mocks -> it still runs and passes offline
    monkeypatch.setenv("AEGIS_JUDGE_BACKEND", "geval")
    monkeypatch.setenv("AEGIS_AGENT_JUDGE_BACKEND", "agent")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    bl = tmp_path / "b.json"
    assert main(["eval", "gate", "--baseline", str(bl), "--update-baseline"]) == 0
    assert main(["eval", "gate", "--baseline", str(bl)]) == 0
