"""Tests for `aegis redteam gate` (invoked in-process, offline, exit-code contract)."""

from __future__ import annotations

from aegis.cli import main
from aegis.evals.persistence import write_baseline
from aegis.redteam.baseline import load_redteam_baseline, redteam_baseline_path


def test_gate_passes_against_committed_baseline(capsys):
    rc = main(["redteam", "gate"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "PASS: no red-team regressions" in out and "mode=mock-offline" in out


def test_update_baseline_then_gate_passes(tmp_path, capsys):
    bl = tmp_path / "rt.json"
    assert main(["redteam", "gate", "--update-baseline", "--baseline", str(bl)]) == 0
    assert bl.exists()
    assert "wrote red-team baseline" in capsys.readouterr().out
    assert main(["redteam", "gate", "--baseline", str(bl)]) == 0


def test_regression_exits_1_and_names_the_attack(tmp_path, capsys):
    # forge a baseline that records a currently-passing gap as BLOCKED -> the fresh
    # hermetic run shows it passing -> attack_now_passing regression (exit 1).
    bl = load_redteam_baseline(redteam_baseline_path("redteam"))
    gap_id = next(aid for aid, a in bl["attacks"].items() if a["outcome"] == "passed")
    cat = bl["attacks"][gap_id]["category"]
    bl["attacks"][gap_id] = {"category": cat, "outcome": "blocked", "code": "prompt_injection"}
    p = tmp_path / "rt.json"
    write_baseline(bl, p)

    rc = main(["redteam", "gate", "--baseline", str(p)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "red-team regression" in err and gap_id in err


def test_missing_baseline_exits_2(tmp_path, capsys):
    rc = main(["redteam", "gate", "--baseline", str(tmp_path / "nope.json")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_id_set_drift_exits_2(tmp_path, capsys):
    bl = load_redteam_baseline(redteam_baseline_path("redteam"))
    bl["attacks"]["ghost-attack"] = {
        "category": "prompt_injection",
        "outcome": "passed",
        "code": None,
    }
    p = tmp_path / "rt.json"
    write_baseline(bl, p)
    rc = main(["redteam", "gate", "--baseline", str(p)])
    assert rc == 2
    assert "attack-set changed" in capsys.readouterr().err


def test_bad_dataset_exits_2(tmp_path, capsys):
    rc = main(["redteam", "gate", "--dataset", str(tmp_path / "nope.jsonl")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_gate_is_offline_under_hostile_env(monkeypatch, capsys):
    # behaviour-flipping env vars must not change the verdict — the gate's input is
    # pinned by build_redteam_settings (init kwargs outrank os.environ).
    monkeypatch.setenv("AEGIS_GUARDRAILS_ENABLED", "false")
    monkeypatch.setenv("AEGIS_GR_INJECTION_ENABLED", "false")
    monkeypatch.setenv("AEGIS_GR_PII_ENGINE", "presidio")
    assert main(["redteam", "gate"]) == 0
    assert "PASS: no red-team regressions" in capsys.readouterr().out
