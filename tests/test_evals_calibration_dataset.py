"""CalibrationCase model + load_calibration loader — offline, no network.

Validation of the cross-field invariants (relevancy<->reference,
faithfulness<->context, human_label<->human_score) and the precise-error JSONL
loader (file:line, dup-id, empty). The shipped 30-case set is checked in its own
test alongside the committed dataset.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from aegis.evals.calibration.dataset import CalibrationDatasetError, load_calibration
from aegis.evals.calibration.models import CalibrationCase


def _rel(**over) -> dict:
    row = {
        "id": "cal-rel-01",
        "criterion_type": "relevancy",
        "criterion": "Is the output relevant to the reference?",
        "output": "Paris is the capital of France.",
        "reference": "The capital of France is Paris.",
        "context": None,
        "human_label": "pass",
        "human_score": 1.0,
    }
    row.update(over)
    return row


def _fai(**over) -> dict:
    row = {
        "id": "cal-fai-01",
        "criterion_type": "faithfulness",
        "criterion": "Is every claim grounded in the context?",
        "output": "Revenue rose 12%.",
        "reference": None,
        "context": ["Revenue rose 12% from Q2."],
        "human_label": "pass",
        "human_score": 1.0,
    }
    row.update(over)
    return row


# --- model validation ------------------------------------------------------- #
def test_valid_relevancy_and_faithfulness_cases():
    assert CalibrationCase.model_validate(_rel()).criterion_type == "relevancy"
    assert CalibrationCase.model_validate(_fai()).criterion_type == "faithfulness"


def test_relevancy_requires_reference_and_no_context():
    with pytest.raises(ValidationError):
        CalibrationCase.model_validate(_rel(reference=None))
    with pytest.raises(ValidationError):
        CalibrationCase.model_validate(_rel(context=["nope"]))


def test_faithfulness_requires_context_and_no_reference():
    with pytest.raises(ValidationError):
        CalibrationCase.model_validate(_fai(context=None))
    with pytest.raises(ValidationError):
        CalibrationCase.model_validate(_fai(reference="nope"))


def test_human_label_score_mismatch_rejected():
    with pytest.raises(ValidationError):
        CalibrationCase.model_validate(_rel(human_label="pass", human_score=0.0))
    with pytest.raises(ValidationError):
        CalibrationCase.model_validate(_rel(human_label="fail", human_score=1.0))


def test_human_score_must_be_zero_or_one():
    with pytest.raises(ValidationError):
        CalibrationCase.model_validate(_rel(human_score=0.5))


def test_integer_human_score_coerces_to_float():
    # a hand-authored JSON `1` (int) must validate as 1.0, not be rejected
    case = CalibrationCase.model_validate(_rel(human_score=1))
    assert case.human_score == 1.0


def test_bad_slug_id_and_extra_field_rejected():
    with pytest.raises(ValidationError):
        CalibrationCase.model_validate(_rel(id="Cal_01"))
    with pytest.raises(ValidationError):
        CalibrationCase.model_validate(_rel(unexpected="x"))


# --- loader ----------------------------------------------------------------- #
def _write(tmp_path, lines):
    p = tmp_path / "cal.jsonl"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def test_load_valid_skips_blank_and_comment_lines(tmp_path):
    p = _write(
        tmp_path,
        ["# a single annotator labeled this set", "", json.dumps(_rel()), json.dumps(_fai())],
    )
    cases = load_calibration(p)
    assert [c.id for c in cases] == ["cal-rel-01", "cal-fai-01"]


def test_missing_file_raises(tmp_path):
    with pytest.raises(CalibrationDatasetError, match="not found"):
        load_calibration(tmp_path / "nope.jsonl")


def test_invalid_json_names_line_and_snippet(tmp_path):
    p = _write(tmp_path, [json.dumps(_rel()), "{not json"])
    with pytest.raises(CalibrationDatasetError, match=r"cal\.jsonl:2: invalid JSON"):
        load_calibration(p)


def test_invalid_field_names_line_and_loc(tmp_path):
    p = _write(tmp_path, [json.dumps(_rel(criterion_type="bogus"))])
    pattern = r"cal\.jsonl:1: invalid case at criterion_type"
    with pytest.raises(CalibrationDatasetError, match=pattern):
        load_calibration(p)


def test_duplicate_id_rejected(tmp_path):
    p = _write(tmp_path, [json.dumps(_rel()), json.dumps(_rel())])
    with pytest.raises(CalibrationDatasetError, match="duplicate case id"):
        load_calibration(p)


def test_empty_dataset_rejected(tmp_path):
    p = _write(tmp_path, ["# only comments", ""])
    with pytest.raises(CalibrationDatasetError, match="contains no cases"):
        load_calibration(p)
