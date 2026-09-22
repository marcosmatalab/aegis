"""Tests for the `aegis calibrate` CLI (invoked in-process, offline)."""

from __future__ import annotations

import json

import pytest

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


# --- --dump-verdicts / --from-verdicts (the offline-reproducibility seam) ---- #


def test_calibrate_dump_verdicts_writes_a_reloadable_artifact(tmp_path, capsys):
    """A run can freeze its own per-case verdicts, and the freeze round-trips to
    the SAME kappa — the property the committed artifact relies on."""
    from aegis.evals.calibration.report import compute_calibration
    from aegis.evals.calibration.verdicts_io import load_verdicts

    dump = tmp_path / "verdicts.jsonl"
    rc = main(
        [
            "calibrate",
            "--judge",
            "mock",
            "--dump-verdicts",
            str(dump),
            "--output",
            str(tmp_path / "c.json"),
        ]
    )
    assert rc == 0
    assert dump.exists()
    assert f"verdicts={dump}" in capsys.readouterr().out

    meta, cases, verdicts = load_verdicts(dump)
    assert meta.judge == "mock"
    # The mock never calls settings.judge_model, so the artifact must not claim it did.
    assert meta.model == "none (keyless mock judge)"
    assert meta.n_cases == 30

    original = json.loads((tmp_path / "c.json").read_text(encoding="utf-8"))
    reloaded = compute_calibration(cases, verdicts, judge=meta.judge, threshold=meta.threshold)
    assert reloaded.global_.result.kappa == original["global"]["kappa"]


def test_calibrate_from_verdicts_on_a_missing_file_exits_2(tmp_path, capsys):
    rc = main(["calibrate", "--from-verdicts", str(tmp_path / "absent.jsonl")])
    assert rc == 2
    assert "not found" in capsys.readouterr().err


@pytest.mark.parametrize(
    "conflicting",
    [
        ["--judge", "mock"],
        ["--dataset", "whatever.jsonl"],
        ["--dump-verdicts", "out.jsonl"],
    ],
)
def test_from_verdicts_rejects_every_judge_selecting_flag(tmp_path, capsys, conflicting):
    """Combining a frozen run with a live judge would silently drop one input."""
    dump = tmp_path / "v.jsonl"
    assert (
        main(
            [
                "calibrate",
                "--judge",
                "mock",
                "--dump-verdicts",
                str(dump),
                "--output",
                str(tmp_path / "c.json"),
            ]
        )
        == 0
    )
    capsys.readouterr()

    rc = main(["calibrate", "--from-verdicts", str(dump), *conflicting])
    assert rc == 2
    assert conflicting[0] in capsys.readouterr().err
