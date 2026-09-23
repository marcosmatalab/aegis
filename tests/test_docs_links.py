"""Personal links in the docs must point at the author, not at a lookalike.

The READMEs linked ``linkedin.com/in/marcosmatagarcia`` — a profile that is not the
author's — for several commits, because nothing checked it. A recruiter clicking the
badge landed on the wrong person. This pins the one correct profile URL across every
tracked text file, and requires both READMEs to carry it, so the link can neither
drift nor be silently dropped.

Companion to ``test_docs_numbers.py``, which pins the published figures.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
LINKEDIN = "https://www.linkedin.com/in/marcos-mata-garc%C3%ADa/"
# shields.io badge label for the display name "Marcos Mata García"
BADGE_LABEL = "Marcos%20Mata%20Garc%C3%ADa"
READMES = ("README.md", "README.es.md")

# Any linkedin.com URL, up to the first character that cannot be part of a URL in
# Markdown/HTML/YAML (whitespace, closing paren/bracket, quote, angle bracket).
LINKEDIN_URL = re.compile(r"https?://(?:[\w-]+\.)?linkedin\.com/[^\s)\]\"'<>]*", re.IGNORECASE)
TEXT_SUFFIXES = {
    ".md",
    ".py",
    ".toml",
    ".yml",
    ".yaml",
    ".json",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".html",
    ".txt",
    ".cfg",
    ".sh",
}


def _tracked_text_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=False)
    if out.returncode != 0:
        pytest.skip("not a git checkout")
    return [
        ROOT / name
        for name in out.stdout.splitlines()
        if Path(name).suffix.lower() in TEXT_SUFFIXES and (ROOT / name).is_file()
    ]


def test_every_linkedin_link_is_the_authors_profile():
    wrong: list[str] = []
    for path in _tracked_text_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            for url in LINKEDIN_URL.findall(line):
                if url != LINKEDIN:
                    wrong.append(f"{path.relative_to(ROOT)}:{lineno}: {url}")
    assert not wrong, f"LinkedIn link is not {LINKEDIN}:\n" + "\n".join(wrong)


def test_the_old_lookalike_handle_appears_nowhere():
    hits = [
        str(p.relative_to(ROOT))
        for p in _tracked_text_files()
        if p != Path(__file__).resolve()
        and "marcosmatagarcia" in p.read_text(encoding="utf-8", errors="ignore").lower()
    ]
    assert not hits, f"the wrong LinkedIn handle is still referenced in: {hits}"


@pytest.mark.parametrize("readme", READMES)
def test_readme_links_the_profile_under_the_real_name(readme):
    text = (ROOT / readme).read_text(encoding="utf-8")
    assert LINKEDIN in text, f"{readme} no longer links the author's LinkedIn"
    assert f"LinkedIn-{BADGE_LABEL}-" in text, (
        f"{readme}: the LinkedIn badge should read 'Marcos Mata García'"
    )
