"""The committed calibration artifact IS the evidence for the README's kappa.

These tests are the tripwire that keeps a published number and its artifact from
drifting apart. They run fully offline: the artifact is a file, and
``compute_calibration`` is pure, so nothing here needs a key, an SDK or a network.

If one of these fails, either the artifact was regenerated (then update the
expected figures AND the README together) or something silently changed the
math (then the README is now lying, which is the exact failure mode the
artifact exists to prevent).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aegis.cli import main
from aegis.evals.calibration.dataset import DEFAULT_CALIBRATION_PATH, load_calibration
from aegis.evals.calibration.kappa import binarize
from aegis.evals.calibration.report import compute_calibration
from aegis.evals.calibration.verdicts_io import dataset_sha256, load_verdicts

ARTIFACT = (
    Path(__file__).resolve().parent.parent / "artifacts" / "calibration-geval-2026-09-22.jsonl"
)

# The three figures the README quotes. Six decimals: tight enough that a real
# change in the math breaks the test, loose enough to survive float formatting.
EXPECTED_GLOBAL_KAPPA = 0.932735
EXPECTED_RELEVANCY_KAPPA = 0.864865
EXPECTED_FAITHFULNESS_KAPPA = 1.0
EXPECTED_GLOBAL_P_O = 0.966667


@pytest.fixture(scope="module")
def frozen():
    return load_verdicts(ARTIFACT)


def test_artifact_is_committed_and_not_ignored():
    """A gitignored artifact is not evidence. reports/ is ignored; artifacts/ is not."""
    assert ARTIFACT.exists(), f"the committed calibration artifact is missing: {ARTIFACT}"


def test_artifact_meta_names_the_run(frozen):
    meta, cases, verdicts = frozen
    assert meta.judge == "geval", "the headline kappa must come from the REAL judge, not the mock"
    assert meta.model == "anthropic/claude-opus-4-8"
    assert meta.threshold == 0.5
    assert meta.n_cases == 30 == len(cases) == len(verdicts)


def test_artifact_matches_the_dataset_it_scored(frozen):
    """Three independent drift guards, checked together.

    The artifact carries its own copy of the human labels so it can be read in
    isolation; that copy is only trustworthy if it still matches the dataset.
    """
    meta, cases, _ = frozen
    assert meta.dataset_sha256 == dataset_sha256(DEFAULT_CALIBRATION_PATH), (
        "calibration.jsonl changed after this artifact was frozen; regenerate the "
        "artifact with --dump-verdicts and update the expected figures"
    )
    dataset = {c.id: c for c in load_calibration()}
    assert [c.id for c in cases] == list(dataset), "artifact ids drifted from the dataset"
    for case in cases:
        assert case.human_label == dataset[case.id].human_label
        assert case.output == dataset[case.id].output


def test_recomputing_the_artifact_reproduces_the_readme_kappa(frozen):
    """The headline number, recomputed from committed bytes. No key, no network."""
    meta, cases, verdicts = frozen
    report = compute_calibration(cases, verdicts, judge=meta.judge, threshold=meta.threshold)

    assert report.global_.result.kappa == pytest.approx(EXPECTED_GLOBAL_KAPPA, abs=5e-7)
    assert report.global_.result.p_o == pytest.approx(EXPECTED_GLOBAL_P_O, abs=5e-7)
    assert report.per_criterion["relevancy"].result.kappa == pytest.approx(
        EXPECTED_RELEVANCY_KAPPA, abs=5e-7
    )
    assert report.per_criterion["faithfulness"].result.kappa == pytest.approx(
        EXPECTED_FAITHFULNESS_KAPPA, abs=5e-7
    )
    assert report.n_parse_failed == 0, "a parse failure is excluded from kappa, so it must be 0"
    assert report.global_.result.band == "almost perfect"


def test_the_single_disagreement_is_the_documented_one(frozen):
    """13/0/1/16, and the one false positive is recoverable and named.

    The README used to say the disagreeing case was not recoverable from the run.
    Persisting the verdicts is what made it recoverable, so the claim is pinned.
    """
    _, cases, verdicts = frozen
    matrix = compute_calibration(cases, verdicts, judge="geval").global_.result.matrix
    # rows=human, cols=judge, positive='pass' -> tp/fn/fp/tn
    assert (matrix.tp, matrix.fn) == (13, 0), "no false negatives: the judge missed no pass"
    assert (matrix.fp, matrix.tn) == (1, 16), "exactly one false positive"

    disagreements = [
        (case, verdict)
        for case, verdict in zip(cases, verdicts, strict=True)
        if binarize(verdict.score, 0.5) != case.human_label
    ]
    assert len(disagreements) == 1
    case, verdict = disagreements[0]
    assert case.id == "cal-rel-05"
    # It sits exactly ON the binarization boundary: the judge expressed a PARTIAL
    # score, and ">= 0.5" rounds that toward pass. Documented in artifacts/README.md.
    assert verdict.score == 0.5
    assert not verdict.parse_failed


def test_cli_from_verdicts_needs_no_key_and_prints_the_number(tmp_path, capsys, monkeypatch):
    """End-to-end on the path a reviewer actually runs."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = tmp_path / "recomputed.json"
    rc = main(["calibrate", "--from-verdicts", str(ARTIFACT), "--output", str(out)])
    assert rc == 0

    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["judge"] == "geval"
    assert report["global"]["kappa"] == pytest.approx(EXPECTED_GLOBAL_KAPPA, abs=5e-7)

    captured = capsys.readouterr()
    assert "kappa=0.933" in captured.out
    assert "model=anthropic/claude-opus-4-8" in captured.out
    # and it says out loud that it did not phone anyone
    assert "no key, no network" in captured.out


def test_from_verdicts_refuses_to_be_combined_with_a_judge(tmp_path, capsys):
    """Passing both an artifact and a judge would silently ignore one of them."""
    rc = main(["calibrate", "--from-verdicts", str(ARTIFACT), "--judge", "mock"])
    assert rc == 2
    assert "--judge" in capsys.readouterr().err
