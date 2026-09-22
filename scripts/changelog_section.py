"""Print one version's section from CHANGELOG.md, for the release body.

Keeps the release notes and the changelog as a single source: the GitHub release
body is generated from the file rather than written twice and allowed to diverge.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def section(text: str, version: str) -> str:
    """The body under ``## [<version>]``, up to the next ``## [`` heading."""
    version = version.lstrip("v")
    lines = text.split("\n")
    start = None
    for i, line in enumerate(lines):
        if re.match(rf"^## \[{re.escape(version)}\]", line):
            start = i
            break
    if start is None:
        raise SystemExit(f"no '## [{version}]' section in the changelog")
    end = len(lines)
    for j in range(start + 1, len(lines)):
        if lines[j].startswith("## ["):
            end = j
            break
    # drop the heading itself and the link-definition footer
    body = [ln for ln in lines[start + 1 : end] if not re.match(r"^\[.+\]: http", ln)]
    return "\n".join(body).strip() + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("version", help="e.g. 0.1.0 or v0.1.0")
    ap.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    args = ap.parse_args()
    body = section(args.changelog.read_text(encoding="utf-8"), args.version)
    # Write bytes, not text: the changelog contains non-ASCII (kappa, arrows) and a
    # Windows console defaults to cp1252, which would raise on it. The release body
    # is UTF-8 regardless of who runs this.
    sys.stdout.buffer.write(body.encode("utf-8"))


if __name__ == "__main__":
    main()
