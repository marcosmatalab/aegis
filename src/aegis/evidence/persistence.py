"""Persist the evidence report as a JSON sidecar (mirrors evals/persistence.py).

The sidecar is the dep-free, auditable twin of the PDF: it keeps the TRUE Unicode
text (ensure_ascii=False) — only the fpdf2 renderer transliterates to latin-1 — so
the JSON is the faithful machine record while the PDF is the human-facing view.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aegis.evidence.models import EvidenceReport


def write_evidence_json(report: EvidenceReport, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return out
