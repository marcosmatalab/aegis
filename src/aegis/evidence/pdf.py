"""Thin fpdf2 renderer for the F8 evidence report.

fpdf2 is OPTIONAL ([reporting] extra): it is lazy-imported inside ``render_pdf`` so
importing this module never requires it (mirrors the otel/anthropic pattern); a
missing extra raises a clean :class:`EvidenceRenderError`, never a bare ImportError.

The renderer ONLY formats ``EvidenceReport`` fields — it computes no numbers. fpdf2's
built-in core fonts are latin-1 only, so :func:`_to_latin1` transliterates the few
non-latin-1 characters our data carries (em/en dashes, curly quotes) to ASCII so a
real value can never crash the render; the JSON sidecar keeps the true Unicode.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from aegis.evidence.mapping import FRAMEWORKS

if TYPE_CHECKING:
    from aegis.evidence.models import EvidenceReport

_TRANSLIT = {
    "—": "-",  # em dash
    "–": "-",  # en dash
    "‘": "'",
    "’": "'",
    "“": '"',
    "”": '"',
    "…": "...",
    "×": "x",  # multiplication sign
    "≥": ">=",
    "κ": "kappa",  # Greek kappa, just in case
}


class EvidenceRenderError(RuntimeError):
    """fpdf2 (the optional [reporting] extra) is not installed."""


def _to_latin1(text: str) -> str:
    """Make text safe for fpdf2 core fonts (latin-1). Transliterate known chars, then
    drop anything still unencodable (so a stray glyph degrades, never crashes)."""
    for src, dst in _TRANSLIT.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


def render_pdf(report: EvidenceReport, path: str | Path) -> Path:
    """Render the evidence report to a PDF at ``path``. Raises EvidenceRenderError if
    fpdf2 is not installed."""
    try:
        from fpdf import FPDF
    except ImportError as exc:  # pragma: no cover - exercised via monkeypatch in tests
        raise EvidenceRenderError(
            'PDF output needs the optional reporting extra: pip install -e ".[reporting]"'
        ) from exc

    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    def line(text: str, *, size: int = 10, style: str = "", h: float = 5.0) -> None:
        pdf.set_font("Helvetica", style, size)
        # new_x/new_y => carriage-return to the left margin (fpdf2's default leaves the
        # cursor at the right edge, which would zero the next multi_cell's width).
        pdf.multi_cell(0, h, text=_to_latin1(text), new_x="LMARGIN", new_y="NEXT")

    def gap(h: float = 2.0) -> None:
        pdf.ln(h)

    # --- cover + disclaimer ---
    line("Aegis - Governance Evidence", size=18, style="B", h=9)
    line(f"suite: {report.suite}    generated (unix): {report.generated}", size=9)
    sc = report.summary_counts
    line(
        f"controls: covered={sc['covered']}  partial={sc['partial']}  "
        f"not_covered={sc['not_covered']}  out_of_scope={sc['out_of_scope']}",
        size=9,
        style="B",
    )
    ip = report.inputs_present
    line(
        "inputs: " + ", ".join(f"{k}={'present' if v else 'absent'}" for k, v in ip.items()),
        size=9,
    )
    gap()
    line(report.disclaimer, size=8, style="I", h=4)
    gap(3)

    # --- per-framework control tables (preserve declared framework order) ---
    for fw in FRAMEWORKS:
        controls = [c for c in report.controls if c.framework == fw]
        if not controls:
            continue
        line(fw, size=13, style="B", h=7)
        for c in controls:
            line(f"[{c.status.upper()}] {c.control_id} - {c.control_title}", size=10, style="B")
            line(f"    source: {c.artifact_source}", size=9)
            if c.derived_value:
                line(f"    evidence: {c.derived_value}", size=9)
            if c.caveat:
                line(f"    caveat: {c.caveat}", size=9, style="I")
            line(f"    control ref: {c.verified_via}", size=7, style="I", h=4)
            gap(1)
        gap(2)

    pdf.output(str(out))
    return out
