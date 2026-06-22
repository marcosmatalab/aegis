"""Persist an eval report as a JSON file.

A run is a single immutable snapshot that maps 1:1 to a JSON document, F3 needs
no querying, and reports/ is already gitignored — so a flat JSON file is the
lightest CI-clean choice. (stdlib sqlite3 would add schema/migration surface for
no benefit until run-history queries are needed, a later phase.)
"""

from __future__ import annotations

import json
from pathlib import Path

from aegis.evals.report import Report

DEFAULT_REPORTS_DIR = Path("reports")


def write_report(report: Report, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return out
