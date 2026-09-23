"""The release story told by the docs must be one the repository can actually deliver.

On 2026-09-23 the CHANGELOG called 0.1.0 the "first tagged release" and told readers to
``pipx install aegis-control-plane`` — while no tag existed, nothing was on PyPI, and
the release workflow carried a PyPI job with no publisher behind it, so it could only
ever fail. Each test below pins one of those claims to something checkable offline:

* no document promises a PyPI install (the project does not publish there);
* every install command is pinned to a version the CHANGELOG lists as released;
* the newest released version in the CHANGELOG is the package version;
* no workflow contains a publish step that has nothing to publish to;
* in a full clone, every released version except the one being cut is a real tag
  on a commit that carries that version.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

import aegis

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
DOCS = [ROOT / "README.md", ROOT / "README.es.md", ROOT / "CHANGELOG.md", ROOT / "CONTRIBUTING.md"]
DOCS += sorted((ROOT / "docs").glob("*.md"))

RELEASED = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", CHANGELOG, re.MULTILINE)
# pip/pipx/uv installing the distribution by bare name (optionally ==version) = from PyPI.
PYPI_INSTALL = re.compile(
    r"\b(?:pipx|pip|uv pip|uv tool) install\s+[\"']?aegis-control-plane\b(?!\S*@)"
)
PINNED_INSTALL = re.compile(r"git\+https://github\.com/marcosmatalab/aegis@v(\d+\.\d+\.\d+)")


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=False)


def test_no_document_promises_a_pypi_install():
    hits = [
        f"{doc.relative_to(ROOT)}:{n}: {line.strip()}"
        for doc in DOCS
        for n, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1)
        if PYPI_INSTALL.search(line)
    ]
    assert not hits, "aegis-control-plane is not published on PyPI:\n" + "\n".join(hits)


def test_every_pinned_install_names_a_released_version():
    for doc in DOCS:
        for version in PINNED_INSTALL.findall(doc.read_text(encoding="utf-8")):
            assert version in RELEASED, (
                f"{doc.relative_to(ROOT)} installs v{version}, which the CHANGELOG never released"
            )


def test_newest_changelog_release_is_the_package_version():
    assert RELEASED, "the CHANGELOG lists no released version"
    assert RELEASED[0] == aegis.__version__, (
        f"CHANGELOG's newest release is {RELEASED[0]} but the package is {aegis.__version__}"
    )
    for version in RELEASED:
        assert f"[{version}]: https://github.com/marcosmatalab/aegis/" in CHANGELOG, (
            f"CHANGELOG has no link reference for [{version}]"
        )


def test_no_workflow_publishes_to_pypi():
    """A publish job with no publisher behind it fails on every tag and proves nothing.

    If the project ever does publish to PyPI, this is the test to change, in the same
    PR that registers the trusted publisher.
    """
    offenders = [
        wf.name
        for wf in sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        if "pypa/gh-action-pypi-publish" in wf.read_text(encoding="utf-8")
        or "twine upload" in wf.read_text(encoding="utf-8")
    ]
    assert not offenders, f"these workflows try to publish to PyPI: {offenders}"


def test_released_versions_are_real_tags():
    if _git("rev-parse", "--is-shallow-repository").stdout.strip() != "false":
        pytest.skip("shallow clone (CI): tags are not fetched")
    for version in RELEASED:
        if version == aegis.__version__:
            continue  # the version being cut is tagged after this commit lands
        sha = _git("rev-list", "-n", "1", f"v{version}")
        assert sha.returncode == 0, (
            f"CHANGELOG releases {version} but tag v{version} does not exist"
        )
        pyproject = _git("show", f"v{version}:pyproject.toml").stdout
        assert f'version = "{version}"' in pyproject, (
            f"tag v{version} points at a commit whose pyproject is not {version}"
        )


def test_release_workflow_runs_for_releases_created_from_the_cli():
    """`gh release create` makes its tag without a push event, so a push-only trigger
    never ran for v0.1.0 and its release got no wheel and no evidence reports."""
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    assert re.search(r"^  release:\n    types: \[published\]", text, re.MULTILINE), (
        "release.yml does not run when a release is published"
    )
    assert re.search(r'^  push:\n    tags: \["v\*"\]', text, re.MULTILINE), (
        "release.yml no longer runs on a pushed v* tag"
    )


def test_pages_redeploys_after_every_release_and_on_demand():
    """The live dashboard is linked from both READMEs, but pages.yml only redeployed on a
    `dashboard/**` change, so nothing refreshed it at release time.

    It hooks the Release workflow through `workflow_run` (which runs on the default
    branch) instead of `release: published` (which runs on the tag), because the
    github-pages environment only accepts deployments from `main`."""
    pages = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    release_name = re.search(r"^name:\s*(.+)$", release, re.MULTILINE)
    assert release_name, "release.yml has no workflow name"

    assert re.search(r"^  workflow_dispatch:", pages, re.MULTILINE), (
        "pages.yml cannot be run by hand"
    )
    hook = re.search(
        r"^  workflow_run:\n    workflows: \[\"([^\"]+)\"\]\n    types: \[completed\]",
        pages,
        re.MULTILINE,
    )
    assert hook, "pages.yml does not redeploy when a release finishes"
    # workflow_run matches by NAME: renaming the Release workflow would silently unhook it
    assert hook.group(1) == release_name.group(1).strip(), (
        f"pages.yml waits for {hook.group(1)!r} but release.yml is named "
        f"{release_name.group(1).strip()!r}"
    )
