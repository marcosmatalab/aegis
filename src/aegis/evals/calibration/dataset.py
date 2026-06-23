"""JSONL loader for the hand-labeled judge-calibration set.

Cloned from ``evals.dataset.load_golden``: blank lines and ``#`` comment lines
are skipped, each remaining line is one JSON ``CalibrationCase``, and malformed
lines raise ``CalibrationDatasetError`` naming the file, 1-based line number,
offending field, and a snippet. Duplicate ids and an empty dataset are errors.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from aegis.evals.calibration.models import CalibrationCase

DEFAULT_CALIBRATION_PATH = Path(__file__).parent.parent / "datasets" / "calibration.jsonl"


class CalibrationDatasetError(ValueError):
    """Raised when the calibration dataset file is missing or malformed."""


def load_calibration(path: str | Path | None = None) -> list[CalibrationCase]:
    """Load and validate calibration cases from a JSONL file."""
    path = Path(path) if path is not None else DEFAULT_CALIBRATION_PATH
    if not path.exists():
        raise CalibrationDatasetError(f"calibration dataset not found: {path}")

    cases: list[CalibrationCase] = []
    seen_ids: set[str] = set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CalibrationDatasetError(
                f"{path}:{lineno}: invalid JSON ({exc.msg}): {line[:80]!r}"
            ) from exc
        try:
            case = CalibrationCase.model_validate(data)
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first.get("loc", ())) or "<root>"
            raise CalibrationDatasetError(
                f"{path}:{lineno}: invalid case at {loc}: {first.get('msg')}: {line[:80]!r}"
            ) from exc
        if case.id in seen_ids:
            raise CalibrationDatasetError(f"{path}:{lineno}: duplicate case id {case.id!r}")
        seen_ids.add(case.id)
        cases.append(case)

    if not cases:
        raise CalibrationDatasetError(f"{path}: contains no cases")
    return cases
