"""JSONL loader for the committed red-team attack catalog.

Cloned from ``evals.dataset.load_golden``: blank/``#`` lines skipped, one JSON
``AttackCase`` per line, precise ``AttackDatasetError`` on malformed lines naming
the file, 1-based line number, offending field, and a snippet; duplicate ids and
an empty dataset are errors.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from aegis.redteam.models import AttackCase

DEFAULT_ATTACKS_PATH = Path(__file__).parent / "datasets" / "attacks.jsonl"


class AttackDatasetError(ValueError):
    """Raised when the attack catalog file is missing or malformed."""


def load_attacks(path: str | Path | None = None) -> list[AttackCase]:
    """Load and validate attack cases from a JSONL file."""
    path = Path(path) if path is not None else DEFAULT_ATTACKS_PATH
    if not path.exists():
        raise AttackDatasetError(f"attack catalog not found: {path}")

    cases: list[AttackCase] = []
    seen_ids: set[str] = set()
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AttackDatasetError(
                f"{path}:{lineno}: invalid JSON ({exc.msg}): {line[:80]!r}"
            ) from exc
        try:
            case = AttackCase.model_validate(data)
        except ValidationError as exc:
            first = exc.errors()[0]
            loc = ".".join(str(p) for p in first.get("loc", ())) or "<root>"
            raise AttackDatasetError(
                f"{path}:{lineno}: invalid case at {loc}: {first.get('msg')}: {line[:80]!r}"
            ) from exc
        if case.id in seen_ids:
            raise AttackDatasetError(f"{path}:{lineno}: duplicate case id {case.id!r}")
        seen_ids.add(case.id)
        cases.append(case)

    if not cases:
        raise AttackDatasetError(f"{path}: contains no cases")
    return cases
