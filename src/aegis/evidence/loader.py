"""Load the real report JSON the evidence builder maps from.

Honest absence vs corruption (mirrors the eval-gate's missing-vs-stale split):
* a NON-EXISTENT default path -> ``None`` -> the dependent controls render
  ``not_covered`` (a documented gap, not an error);
* a NON-EXISTENT path the user EXPLICITLY passed -> ``EvidenceInputError`` (a typo'd
  path should not silently vanish into not-covered);
* a PRESENT but unreadable/corrupt file (default OR explicit) -> ``EvidenceInputError``
  (you found a file, it is broken — never silently treat it as absent or fabricate).
The CLI maps ``EvidenceInputError`` to exit 2.
"""

from __future__ import annotations

import json
from pathlib import Path


class EvidenceInputError(ValueError):
    """A report path was explicitly given but missing, or a present file is corrupt."""


def read_report(path: Path, *, required: bool = False) -> dict | None:
    """Read one report JSON. ``required`` (the path was explicitly passed) makes a
    missing file an error; otherwise a missing file is ``None``. A present-but-corrupt
    or non-object file is always an error."""
    if not path.exists():
        if required:
            raise EvidenceInputError(f"report not found: {path}")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise EvidenceInputError(f"{path}: unreadable/corrupt report ({exc})") from exc
    if not isinstance(data, dict):
        raise EvidenceInputError(f"{path}: report is not a JSON object")
    return data
