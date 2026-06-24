"""fpdf2 renderer: latin-1 transliteration (pure), a valid PDF is produced offline,
non-latin-1 data never crashes the render, and a missing extra raises cleanly."""

from __future__ import annotations

import importlib.util

import pytest

from aegis.evidence.builder import build_evidence
from aegis.evidence.pdf import EvidenceRenderError, _to_latin1, render_pdf
from aegis.gateway.config import Settings

_HAS_FPDF = importlib.util.find_spec("fpdf") is not None
_needs_fpdf = pytest.mark.skipif(not _HAS_FPDF, reason="requires the optional [reporting] extra")


def test_transliterate_is_pure_and_latin1_safe():
    assert _to_latin1("A.2–A.5 — V&V") == "A.2-A.5 - V&V"  # en + em dash -> hyphen
    assert _to_latin1("token×price ≥ 0") == "tokenxprice >= 0"  # mapped chars, no added spaces
    # a truly non-latin-1, non-mapped glyph degrades to '?' rather than raising
    assert "?" in _to_latin1("emoji \U0001f600 here")
    # plain ASCII is unchanged
    assert _to_latin1("plain ascii") == "plain ascii"


@_needs_fpdf
def test_render_produces_a_valid_pdf(tmp_path):
    rep = build_evidence(
        eval_report=None,
        redteam_report=None,
        calibration_report=None,
        settings=Settings(_env_file=None, guardrails_enabled=True),
    )
    out = render_pdf(rep, tmp_path / "evidence.pdf")
    data = out.read_bytes()
    assert data.startswith(b"%PDF-") and len(data) > 800


@_needs_fpdf
def test_render_does_not_crash_on_non_latin1_data(tmp_path):
    # the mapping's out-of-scope rows carry an em-dash artifact_source / en-dash id;
    # rendering them must not raise UnicodeEncodeError (the latin-1 trap the review caught)
    rep = build_evidence(
        eval_report=None,
        redteam_report=None,
        calibration_report=None,
        settings=Settings(_env_file=None),
    )
    assert any("—" in c.artifact_source or "–" in c.control_id for c in rep.controls)
    out = render_pdf(rep, tmp_path / "evidence.pdf")
    assert out.read_bytes().startswith(b"%PDF-")


def test_missing_fpdf_raises_clean_error(monkeypatch, tmp_path):
    # simulate the [reporting] extra being absent -> a clean, actionable error
    import builtins

    real_import = builtins.__import__

    def _no_fpdf(name, *args, **kwargs):
        if name == "fpdf" or name.startswith("fpdf."):
            raise ImportError("No module named 'fpdf'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _no_fpdf)
    rep = build_evidence(
        eval_report=None,
        redteam_report=None,
        calibration_report=None,
        settings=Settings(_env_file=None),
    )
    with pytest.raises(EvidenceRenderError, match=r"\[reporting\]"):
        render_pdf(rep, tmp_path / "evidence.pdf")
