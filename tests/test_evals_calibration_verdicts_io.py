"""Round-trip and failure-mode tests for the frozen-verdicts artifact format.

The artifact is the evidence for a published number, so every way it can be
wrong has to fail LOUDLY rather than silently recompute a different kappa. These
tests pin that: a clean round-trip must be exact, and each corruption must raise
``VerdictsFileError`` naming the file and line.
"""

from __future__ import annotations

import json

import pytest

from aegis.evals.calibration.dataset import DEFAULT_CALIBRATION_PATH, load_calibration
from aegis.evals.calibration.report import compute_calibration
from aegis.evals.calibration.verdicts_io import (
    FORMAT_VERSION,
    VerdictsFileError,
    dataset_sha256,
    dump_verdicts,
    load_verdicts,
    write_verdicts,
)
from aegis.evals.judge.base import JudgeVerdict


@pytest.fixture(scope="module")
def cases():
    return load_calibration()


@pytest.fixture(scope="module")
def verdicts(cases):
    """Deterministic synthetic verdicts: agree with every human label except one,
    and mark one as a parse failure, so the round-trip exercises both flags."""
    out = []
    for i, case in enumerate(cases):
        score = 1.0 if case.human_label == "pass" else 0.0
        if i == 3:  # one deliberate disagreement
            score = 1.0 - score
        out.append(
            JudgeVerdict(
                score=score,
                reasoning=f"synthetic reasoning {i}",
                criteria=case.criterion,
                judge="geval",
                parse_failed=(i == 7),
            )
        )
    return out


def _dump(cases, verdicts, **over):
    kwargs = {
        "judge": "geval",
        "model": "anthropic/claude-opus-4-8",
        "created": 1790077174,
        "dataset": DEFAULT_CALIBRATION_PATH,
        "threshold": 0.5,
    }
    kwargs.update(over)
    return dump_verdicts(cases, verdicts, **kwargs)


def _write(tmp_path, text, name="v.jsonl"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


# --- round trip ------------------------------------------------------------ #


def test_round_trip_preserves_every_field(tmp_path, cases, verdicts):
    path = _write(tmp_path, _dump(cases, verdicts))
    meta, loaded_cases, loaded_verdicts = load_verdicts(path)

    assert meta.judge == "geval"
    assert meta.model == "anthropic/claude-opus-4-8"
    assert meta.created == 1790077174
    assert meta.threshold == 0.5
    assert meta.format_version == FORMAT_VERSION
    assert meta.dataset == DEFAULT_CALIBRATION_PATH.name
    assert meta.dataset_sha256 == dataset_sha256(DEFAULT_CALIBRATION_PATH)

    assert [c.id for c in loaded_cases] == [c.id for c in cases]
    assert [c.human_label for c in loaded_cases] == [c.human_label for c in cases]
    assert [c.reference for c in loaded_cases] == [c.reference for c in cases]
    assert [c.context for c in loaded_cases] == [c.context for c in cases]
    assert [v.score for v in loaded_verdicts] == [v.score for v in verdicts]
    assert [v.parse_failed for v in loaded_verdicts] == [v.parse_failed for v in verdicts]
    assert [v.reasoning for v in loaded_verdicts] == [v.reasoning for v in verdicts]


def test_round_trip_reproduces_the_same_kappa(tmp_path, cases, verdicts):
    """The property that actually matters: a reload recomputes bit-identically."""
    direct = compute_calibration(cases, verdicts, judge="geval")
    meta, rc, rv = load_verdicts(_write(tmp_path, _dump(cases, verdicts)))
    reloaded = compute_calibration(rc, rv, judge=meta.judge, threshold=meta.threshold)

    assert reloaded.global_.result.kappa == direct.global_.result.kappa
    assert reloaded.global_.result.p_o == direct.global_.result.p_o
    assert reloaded.n_parse_failed == direct.n_parse_failed == 1


def test_write_verdicts_creates_parent_directories(tmp_path, cases, verdicts):
    out = tmp_path / "nested" / "deeper" / "v.jsonl"
    written = write_verdicts(
        out,
        cases,
        verdicts,
        judge="geval",
        model="m",
        created=1,
        dataset=DEFAULT_CALIBRATION_PATH,
        threshold=0.5,
    )
    assert written == out and out.exists()
    assert load_verdicts(out)[0].judge == "geval"


def test_blank_and_comment_lines_are_skipped(tmp_path, cases, verdicts):
    text = _dump(cases, verdicts)
    head, rest = text.split("\n", 1)
    decorated = f"# a human-readable header\n{head}\n\n# mid-file note\n{rest}"
    assert load_verdicts(_write(tmp_path, decorated))[0].n_cases == len(cases)


def test_dump_rejects_misaligned_inputs(cases, verdicts):
    with pytest.raises(ValueError, match="align 1:1"):
        _dump(cases, verdicts[:-1])


def test_dump_emits_exactly_one_grounding_per_row(cases, verdicts):
    """CalibrationCase forbids carrying both, so the artifact must not either."""
    for line in _dump(cases, verdicts).splitlines()[1:]:
        row = json.loads(line)
        assert ("reference" in row) ^ ("context" in row), row["id"]


# --- failure modes --------------------------------------------------------- #


def test_missing_file_is_named(tmp_path):
    with pytest.raises(VerdictsFileError, match="not found"):
        load_verdicts(tmp_path / "nope.jsonl")


def test_invalid_json_names_the_line(tmp_path, cases, verdicts):
    text = _dump(cases, verdicts) + "{not json\n"
    with pytest.raises(VerdictsFileError, match="invalid JSON"):
        load_verdicts(_write(tmp_path, text))


def test_non_object_line_is_rejected(tmp_path, cases, verdicts):
    with pytest.raises(VerdictsFileError, match="expected a JSON object"):
        load_verdicts(_write(tmp_path, _dump(cases, verdicts) + "[1, 2, 3]\n"))


def test_unknown_record_type_is_rejected(tmp_path, cases, verdicts):
    text = _dump(cases, verdicts) + json.dumps({"record": "footnote"}) + "\n"
    with pytest.raises(VerdictsFileError, match="unknown record type"):
        load_verdicts(_write(tmp_path, text))


def test_duplicate_meta_is_rejected(tmp_path, cases, verdicts):
    lines = _dump(cases, verdicts).splitlines()
    with pytest.raises(VerdictsFileError, match="duplicate meta"):
        load_verdicts(_write(tmp_path, "\n".join([*lines, lines[0]]) + "\n"))


def test_meta_after_verdicts_is_rejected(tmp_path, cases, verdicts):
    lines = _dump(cases, verdicts).splitlines()
    reordered = [lines[1], lines[0], *lines[2:]]
    with pytest.raises(VerdictsFileError, match="meta must precede|before the meta"):
        load_verdicts(_write(tmp_path, "\n".join(reordered) + "\n"))


def test_verdict_without_meta_is_rejected(tmp_path, cases, verdicts):
    body = _dump(cases, verdicts).splitlines()[1:]
    with pytest.raises(VerdictsFileError, match="before the meta record"):
        load_verdicts(_write(tmp_path, "\n".join(body) + "\n"))


def test_malformed_meta_is_rejected(tmp_path, cases, verdicts):
    lines = _dump(cases, verdicts).splitlines()
    broken = json.loads(lines[0])
    del broken["dataset_sha256"]
    with pytest.raises(VerdictsFileError, match="malformed meta"):
        load_verdicts(_write(tmp_path, "\n".join([json.dumps(broken), *lines[1:]]) + "\n"))


def test_file_with_no_meta_at_all_is_rejected(tmp_path):
    with pytest.raises(VerdictsFileError, match="no meta record"):
        load_verdicts(_write(tmp_path, "# only a comment\n\n"))


def test_meta_with_no_verdicts_is_rejected(tmp_path, cases, verdicts):
    meta_line = _dump(cases, verdicts).splitlines()[0]
    with pytest.raises(VerdictsFileError, match="no verdict records"):
        load_verdicts(_write(tmp_path, meta_line + "\n"))


def test_case_count_mismatch_is_rejected(tmp_path, cases, verdicts):
    """A truncated artifact must not quietly recompute over fewer cases."""
    lines = _dump(cases, verdicts).splitlines()
    with pytest.raises(VerdictsFileError, match="n_cases=30 but the file holds 5"):
        load_verdicts(_write(tmp_path, "\n".join(lines[:6]) + "\n"))


def test_duplicate_case_id_is_rejected(tmp_path, cases, verdicts):
    lines = _dump(cases, verdicts).splitlines()
    dupe = [*lines, lines[1]]
    dupe[0] = json.dumps({**json.loads(lines[0]), "n_cases": len(cases) + 1})
    with pytest.raises(VerdictsFileError, match="duplicate case id"):
        load_verdicts(_write(tmp_path, "\n".join(dupe) + "\n"))


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        ({"judge_score": "high"}, "missing/invalid 'judge_score'"),
        ({"judge_score": 1.5}, "outside 0..1"),
        ({"judge_score": -0.1}, "outside 0..1"),
        ({"parse_failed": "yes"}, "must be a boolean"),
        ({"human_label": "maybe"}, "invalid case"),
        ({"human_score": 0.0}, "invalid case"),  # inconsistent with human_label 'pass'
        ({"id": "Not A Slug"}, "invalid case"),
    ],
)
def test_corrupt_verdict_row_is_rejected(tmp_path, cases, verdicts, mutation, match):
    """Every field a hand edit could break is validated, not trusted."""
    lines = _dump(cases, verdicts).splitlines()
    row = {**json.loads(lines[1]), **mutation}
    lines[1] = json.dumps(row)
    with pytest.raises(VerdictsFileError, match=match):
        load_verdicts(_write(tmp_path, "\n".join(lines) + "\n"))


def test_missing_judge_score_key_is_rejected(tmp_path, cases, verdicts):
    lines = _dump(cases, verdicts).splitlines()
    row = json.loads(lines[1])
    del row["judge_score"]
    lines[1] = json.dumps(row)
    with pytest.raises(VerdictsFileError, match="missing/invalid 'judge_score'"):
        load_verdicts(_write(tmp_path, "\n".join(lines) + "\n"))


def test_dataset_sha256_is_content_addressed(tmp_path):
    a = tmp_path / "a.jsonl"
    b = tmp_path / "b.jsonl"
    a.write_text("same bytes", encoding="utf-8")
    b.write_text("same bytes", encoding="utf-8")
    assert dataset_sha256(a) == dataset_sha256(b)
    b.write_text("other bytes", encoding="utf-8")
    assert dataset_sha256(a) != dataset_sha256(b)
