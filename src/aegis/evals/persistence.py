"""Persist an eval report as a JSON file.

A run is a single immutable snapshot that maps 1:1 to a JSON document, F3 needs
no querying, and reports/ is already gitignored — so a flat JSON file is the
lightest CI-clean choice. (stdlib sqlite3 would add schema/migration surface for
no benefit until run-history queries are needed, a later phase.)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from aegis.evals.report import Report

if TYPE_CHECKING:
    from aegis.evals.calibration.report import CalibrationReport
    from aegis.redteam.report import RedTeamReport

DEFAULT_REPORTS_DIR = Path("reports")


def write_report(report: Report, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def write_calibration_report(report: CalibrationReport, path: str | Path) -> Path:
    """Persist a calibration report as JSON (mirrors write_report). The report's
    to_dict() serializes an undefined kappa/p_o/p_e as JSON null, never NaN."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def write_redteam_report(report: RedTeamReport, path: str | Path) -> Path:
    """Persist a red-team report as JSON (mirrors write_report)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    return out


def write_baseline(baseline: dict, path: str | Path) -> Path:
    """Persist a gate baseline (the committed eval-gate contract) as JSON.

    Sorted keys + a trailing newline keep the committed artifact's diff stable and
    reviewable (key order is independent of golden-file order)."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(baseline, indent=2, ensure_ascii=False, sort_keys=True)
    out.write_text(text + "\n", encoding="utf-8")
    return out
