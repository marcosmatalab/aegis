"""Every figure quoted in the READMEs must match the thing that produces it.

The rule this enforces: **no number is hand-written into the README if a command
prints it.** That rule is easy to state and easy to break — the test count sat at
944 for several commits after the suite had grown to 952, and an external reader
found it before CI did, because nothing was checking.

Each test below recomputes a published figure from its real source (the committed
baselines, the frozen calibration artifact, the attack catalog, this pytest
session) and asserts the README text agrees, in BOTH languages. A stale figure is
now a red build rather than something a reviewer has to catch by eye.

Companion to ``test_docs_demo_gif.py``, which pins the same kind of claim about
the demo GIF.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

from aegis.evals.calibration.report import compute_calibration
from aegis.evals.calibration.verdicts_io import load_verdicts
from aegis.redteam.dataset import load_attacks
from aegis.redteam.runner import run_redteam

ROOT = Path(__file__).resolve().parent.parent
READMES = {"en": ROOT / "README.md", "es": ROOT / "README.es.md"}
ARTIFACT = ROOT / "artifacts" / "calibration-geval-2026-09-22.jsonl"
EVAL_BASELINE = ROOT / "src" / "aegis" / "evals" / "baselines" / "golden.json"


@pytest.fixture(scope="module")
def readmes() -> dict[str, str]:
    return {lang: path.read_text(encoding="utf-8") for lang, path in READMES.items()}


def _assert_in_both(readmes: dict[str, str], needle: str, why: str) -> None:
    for lang, text in readmes.items():
        assert needle in text, f"README.{lang}: {why} — expected to find {needle!r}"


# --- the three headline numbers -------------------------------------------- #


def test_redteam_figures_match_a_real_run(readmes):
    """`aegis redteam run` is offline and ~1s, so the README's rate is recomputable
    here rather than trusted."""
    report = run_redteam(load_attacks(), created=0)
    # `caught` = blocked + redacted, summed from the per-category stats, which is the
    # same arithmetic the report prints and the dashboard renders.
    caught = sum(c.blocked + c.redacted for c in report.categories.values())
    total = report.case_count
    gaps = len(report.known_gaps)

    _assert_in_both(readmes, f"{caught}/{total}", "the red-team detection fraction is stale")

    # The two languages format decimals differently, so they are checked separately.
    en, es = readmes["en"], readmes["es"]
    assert f"{report.overall_detection_rate:.3f}" in en, "README.md detection rate is stale"
    assert f"{report.overall_detection_rate:.3f}".replace(".", ",") in es, (
        "README.es.md detection rate is stale (Spanish uses a decimal comma)"
    )
    # The gap count is the honesty claim, so it is pinned too: a disclosed gap that
    # never reaches the README would quietly inflate the apparent coverage.
    assert re.search(rf"\b{gaps}\b[^\n]*gaps? (?:are named|named)", en), (
        f"README.md does not say {gaps} named gaps"
    )
    assert re.search(rf"\b{gaps}\b[^\n]*gaps nombrados|\b{gaps}\b[^\n]*que pasan", es), (
        f"README.es.md does not say {gaps} named gaps"
    )


def test_eval_figures_match_the_committed_baseline(readmes):
    """The baseline IS the contract, so the README must quote it, not a memory of it."""
    baseline = json.loads(EVAL_BASELINE.read_text(encoding="utf-8"))
    overall = baseline["overall_score"]
    levels = {k: v["mean_score"] for k, v in baseline["levels"].items()}

    en, es = readmes["en"], readmes["es"]
    assert f"{overall:.3f}" in en, f"README.md overall score is stale (baseline says {overall:.3f})"
    assert f"{overall:.3f}".replace(".", ",") in es, "README.es.md overall score is stale"
    for level, mean in levels.items():
        assert f"{mean:.3f}" in en, f"README.md {level} mean is stale (baseline says {mean:.3f})"


def test_kappa_figures_match_the_frozen_artifact(readmes):
    """The κ is the number most worth protecting: it is the one a reader cannot
    recompute without the artifact, so a drift here is invisible to them."""
    meta, cases, verdicts = load_verdicts(ARTIFACT)
    report = compute_calibration(cases, verdicts, judge=meta.judge, threshold=meta.threshold)

    global_k = report.global_.result.kappa
    assert global_k is not None
    expected = f"{global_k:.3f}"

    # EVERY κ figure must be right, not merely one of them. Checking `expected in
    # text` would pass while a second mention drifted — which is exactly what a
    # deliberate mutation test showed: changing one of the three occurrences left
    # the assertion green. So collect all of them and compare the set.
    pattern = re.compile(r"(?:κ|kappa)[^0-9]{0,12}([0-9][.,][0-9]{2,3})", re.IGNORECASE)
    for lang, text in readmes.items():
        found = {
            m.group(1).replace(",", ".")
            for line in text.splitlines()
            for m in pattern.finditer(line)
        }
        assert found, f"README.{lang} states no κ value at all"
        stale = found - {expected}
        assert not stale, (
            f"README.{lang} quotes κ as {sorted(stale)} but the committed artifact "
            f"recomputes to {expected}"
        )

    _assert_in_both(readmes, f"N={report.n_cases}", "the calibration N is stale")


# --- the suite's own size --------------------------------------------------- #


def _is_full_run(request: pytest.FixtureRequest) -> bool:
    """A filtered run collects a subset, which would make the count assertion lie.

    Only a full, unfiltered collection can be compared against the published total.
    """
    opt = request.config.option
    if getattr(opt, "keyword", "") or getattr(opt, "markexpr", ""):
        return False
    args = [a for a in request.config.args if not a.startswith("-")]
    return args in ([], ["tests"], [str(ROOT / "tests")])


def test_readme_test_count_matches_this_session(request, readmes):
    """`952 passed, 4 skipped` has to equal what pytest actually collected.

    Read from the live session rather than by shelling out to pytest again: exact,
    free, and impossible to get out of step with the run doing the asserting.
    """
    if not _is_full_run(request):
        pytest.skip("partial/filtered run — the collected count is not the suite total")

    collected = len(request.session.items)
    en = readmes["en"]
    m = re.search(r"\*\*(\d+) passed, (\d+) skipped\*\*", en)
    assert m, "README.md no longer states '**N passed, M skipped**'"
    passed, skipped = int(m.group(1)), int(m.group(2))

    assert passed + skipped == collected, (
        f"README.md says {passed} passed + {skipped} skipped = {passed + skipped}, "
        f"but pytest collected {collected}. Update the README (3 places) or the suite."
    )
    # the same total, spelled three different ways, must agree with itself
    assert f"{passed} tests" in en, f"README.md 'N tests' disagrees with '{passed} passed'"
    assert f"{passed} passed, {skipped} skipped" in readmes["es"], "README.es.md count is stale"
    assert f"{passed} tests" in readmes["es"] or f"{passed} pasan" in readmes["es"]
    # the badge and the key-metrics cell restate it too; a stale badge is the most
    # visible number on the page, so every spelling is pinned, in both languages
    for lang, text in readmes.items():
        badges = set(re.findall(r"badge/tests-(\d+)%20passing", text))
        assert badges == {str(passed)}, f"README.{lang} tests badge says {badges}, not {passed}"
        cells = set(re.findall(r"^\| \*\*(\d+)\*\* \| \*\*\d+%\*\*", text, re.MULTILINE))
        assert cells == {str(passed)}, f"README.{lang} key-metrics row says {cells}, not {passed}"


def test_readme_coverage_claim_is_at_least_the_enforced_floor(readmes):
    """The README may not claim coverage the gate would not actually enforce."""
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    m = re.search(r"--cov-fail-under=(\d+)", ci)
    assert m, "the coverage floor is no longer set in ci.yml"
    floor = int(m.group(1))
    assert pyproject["tool"]["coverage"]["run"]["branch"] is True, "branch coverage is off"

    for lang, text in readmes.items():
        claimed = re.search(
            r"(\d+)% (?:branch coverage|de cobertura de rama|cobertura de rama)", text
        )
        assert claimed, f"README.{lang} no longer states a branch-coverage percentage"
        assert int(claimed.group(1)) >= floor, (
            f"README.{lang} claims {claimed.group(1)}% but CI only enforces {floor}%"
        )


# --- provenance ------------------------------------------------------------- #


def test_provenance_declares_every_working_day(readmes):
    """The provenance section tells the reader to run a command; its output must not
    contain a day the section never mentions.

    This is the check that was missing when the section declared June and the log
    had started printing September.
    """
    import subprocess

    out = subprocess.run(
        ["git", "log", "--format=%ad", "--date=short"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if out.returncode != 0:
        pytest.skip("not a git checkout")

    months = {d[:7] for d in out.stdout.split() if d}
    assert months, "git log produced no dates"
    for month in sorted(months):
        year, mm = month.split("-")
        name_en = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ][int(mm) - 1]
        assert name_en in readmes["en"] or month in readmes["en"], (
            f"README.md's provenance section never mentions {name_en} {year}, but the "
            f"git log it tells the reader to run prints commits from {month}"
        )
