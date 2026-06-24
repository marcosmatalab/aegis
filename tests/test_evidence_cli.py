"""`aegis evidence` CLI: PDF/JSON output, exit 0/2, not-covered echo, and the
--format json path never needing fpdf2. Each test chdirs to a tmp dir so the repo's
own reports/ never leaks in (the default report paths are relative)."""

from __future__ import annotations

import builtins
import importlib.util
import json

import pytest

from aegis.cli import main

_HAS_FPDF = importlib.util.find_spec("fpdf") is not None
_needs_fpdf = pytest.mark.skipif(not _HAS_FPDF, reason="requires the optional [reporting] extra")


def _eval():
    return {
        "suite": "golden",
        "judge": "geval",
        "case_count": 2,
        "created": 0,
        "levels": {"L1": {"mean_score": 1.0, "passed": 2, "scored": 2}},
        "overall_score": 1.0,
        "clear": {
            "accuracy": {"status": "measured", "value": 1.0},
            "reliability": {"status": "measured", "value": 1.0},
            "efficiency": {"status": "measured", "value": 1.0},
            "cost": {"status": "placeholder", "value": None},
            "latency": {"status": "placeholder", "value": None},
        },
    }


def _write(path, obj):
    path.write_text(json.dumps(obj), encoding="utf-8")
    return path


def _block_fpdf(monkeypatch):
    real = builtins.__import__

    def _no_fpdf(name, *args, **kwargs):
        if name == "fpdf" or name.startswith("fpdf."):
            raise ImportError("No module named 'fpdf'")
        return real(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_fpdf)


@_needs_fpdf
def test_evidence_pdf_exit0_with_a_real_report(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    ep = _write(tmp_path / "eval-golden.json", _eval())
    out = tmp_path / "evidence.pdf"
    rc = main(["evidence", "--eval", str(ep), "--output", str(out)])
    assert rc == 0
    assert out.read_bytes().startswith(b"%PDF-")
    assert "covered=" in capsys.readouterr().out


def test_evidence_json_format_needs_no_fpdf2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _block_fpdf(monkeypatch)  # even with fpdf2 unimportable, --format json must work
    ep = _write(tmp_path / "eval-golden.json", _eval())
    out = tmp_path / "evidence.json"
    rc = main(["evidence", "--format", "json", "--eval", str(ep), "--output", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "controls" in data and "summary_counts" in data


def test_absent_reports_echo_not_covered_and_still_exit0(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)  # empty cwd => all default report paths are absent
    out = tmp_path / "evidence.json"
    rc = main(["evidence", "--format", "json", "--output", str(out)])
    assert rc == 0  # a partial pack is still valid
    err = capsys.readouterr().err
    assert "not covered" in err
    assert "aegis eval run" in err  # the produce-it hint is surfaced


def test_corrupt_explicit_report_is_exit2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    bad = tmp_path / "bad.json"
    bad.write_text("{not valid json", encoding="utf-8")
    rc = main(["evidence", "--eval", str(bad)])
    assert rc == 2
    assert "error" in capsys.readouterr().err


def test_missing_explicit_report_is_exit2(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = main(["evidence", "--eval", str(tmp_path / "nope.json")])
    assert rc == 2


def test_pdf_format_without_fpdf2_is_exit2(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _block_fpdf(monkeypatch)
    rc = main(["evidence", "--format", "pdf", "--output", str(tmp_path / "e.pdf")])
    assert rc == 2
    assert "[reporting]" in capsys.readouterr().err
