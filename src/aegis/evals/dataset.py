"""JSONL golden-dataset loader with precise, actionable error messages."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from aegis.evals.models import EvalCase

DEFAULT_GOLDEN_PATH = Path(__file__).parent / "datasets" / "golden.jsonl"


class GoldenDatasetError(ValueError):
    """Raised when the golden dataset file is missing or malformed."""


def load_golden(path: str | Path | None = None) -> list[EvalCase]:
    """Load and validate eval cases from a JSONL file.

    Blank lines and ``#`` comment lines are skipped. Each remaining line must be
    one JSON ``EvalCase``. Malformed lines raise ``GoldenDatasetError`` naming the
    file, 1-based line number, offending field, and a snippet. Duplicate ids and
    an empty dataset are errors.
    """
    path = Path(path) if path is not None else DEFAULT_GOLDEN_PATH
    if not path.exists():
        raise GoldenDatasetError(f"golden dataset not found: {path}")

    cases: list[EvalCase] = []
    seen_ids: set[str] = set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise GoldenDatasetError(
                f"{path}:{lineno}: invalid JSON ({exc.msg}): {line[:80]!r}"
            ) from exc
        try:
            case = EvalCase.model_validate(data)
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first.get("loc", ())) or "<root>"
            raise GoldenDatasetError(
                f"{path}:{lineno}: invalid case at {loc}: {first.get('msg')}: {line[:80]!r}"
            ) from exc
        if case.id in seen_ids:
            raise GoldenDatasetError(f"{path}:{lineno}: duplicate case id {case.id!r}")
        seen_ids.add(case.id)
        cases.append(case)

    if not cases:
        raise GoldenDatasetError(f"{path}: contains no cases")
    return cases
