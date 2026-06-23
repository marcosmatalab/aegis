"""compute_calibration — pure agreement over fixture verdicts (no judge/network).

Per-criterion split, parse_failed exclusion (byte-identical to dropping the
rows), the n_valid + n_parse_failed == n_cases invariant, the strict-zip length
guard, and JSON serialization (named cells, 'global' key, null when degenerate).
"""

from __future__ import annotations

import json

import pytest

from aegis.evals.calibration.models import CalibrationCase
from aegis.evals.calibration.report import compute_calibration
from aegis.evals.judge.base import JudgeVerdict


def _case(cid: str, ctype: str, label: str) -> CalibrationCase:
    score = 1.0 if label == "pass" else 0.0
    common = {
        "id": cid,
        "criterion_type": ctype,
        "criterion": "c",
        "output": "o",
        "human_label": label,
        "human_score": score,
    }
    if ctype == "relevancy":
        common |= {"reference": "r", "context": None}
    else:
        common |= {"reference": None, "context": ["c"]}
    return CalibrationCase.model_validate(common)


def _v(score: float, *, parse_failed: bool = False) -> JudgeVerdict:
    return JudgeVerdict(score, "reason", "crit", "geval", parse_failed=parse_failed)


# --- per-criterion split ---------------------------------------------------- #
def test_per_criterion_kappa_can_diverge_and_global_aggregates():
    cases = [
        _case("cal-rel-01", "relevancy", "pass"),
        _case("cal-rel-02", "relevancy", "pass"),
        _case("cal-rel-03", "relevancy", "fail"),
        _case("cal-rel-04", "relevancy", "fail"),
        _case("cal-fai-01", "faithfulness", "pass"),
        _case("cal-fai-02", "faithfulness", "pass"),
        _case("cal-fai-03", "faithfulness", "fail"),
        _case("cal-fai-04", "faithfulness", "fail"),
    ]
    verdicts = [
        _v(0.9), _v(0.9), _v(0.1), _v(0.1),  # relevancy: perfect agreement -> 1.0
        _v(0.1), _v(0.9), _v(0.9), _v(0.1),  # faithfulness: chance -> 0.0
    ]  # fmt: skip
    report = compute_calibration(cases, verdicts, judge="geval")
    assert report.per_criterion["relevancy"].result.kappa == pytest.approx(1.0)
    assert report.per_criterion["faithfulness"].result.kappa == pytest.approx(0.0)
    assert report.global_.result.kappa == pytest.approx(0.5)


# --- parse_failed exclusion ------------------------------------------------- #
def test_parse_failed_excluded_equals_dropping_the_row():
    base_cases = [
        _case("cal-rel-01", "relevancy", "pass"),
        _case("cal-rel-02", "relevancy", "pass"),
        _case("cal-rel-03", "relevancy", "fail"),
        _case("cal-rel-04", "relevancy", "fail"),
    ]
    base_verdicts = [_v(0.9), _v(0.9), _v(0.1), _v(0.1)]
    clean = compute_calibration(base_cases, base_verdicts, judge="geval")

    # add a 5th case whose verdict parse-failed at the neutral 0.5 (which would
    # binarize to 'pass' if it were wrongly included)
    with_pf_cases = base_cases + [_case("cal-rel-05", "relevancy", "fail")]
    with_pf_verdicts = base_verdicts + [_v(0.5, parse_failed=True)]
    got = compute_calibration(with_pf_cases, with_pf_verdicts, judge="geval")

    rel = got.per_criterion["relevancy"]
    # kappa + matrix identical to the clean run; the parse failure changed nothing
    assert rel.result.kappa == clean.per_criterion["relevancy"].result.kappa
    assert rel.result.matrix == clean.per_criterion["relevancy"].result.matrix
    # but it is counted and excluded, not averaged in
    assert rel.n_cases == 5
    assert rel.n_parse_failed == 1
    assert rel.result.n_valid == 4


def test_all_parse_failed_slice_is_undefined_not_a_crash():
    cases = [_case("cal-rel-01", "relevancy", "pass"), _case("cal-rel-02", "relevancy", "fail")]
    verdicts = [_v(0.5, parse_failed=True), _v(0.5, parse_failed=True)]
    report = compute_calibration(cases, verdicts, judge="geval")
    rel = report.per_criterion["relevancy"]
    assert rel.result.kappa is None
    assert rel.result.p_o is None  # nothing judgeable -> not a fabricated 0.0
    assert rel.n_parse_failed == 2 and rel.result.n_valid == 0


# --- invariants ------------------------------------------------------------- #
def test_counts_invariant_per_scope_and_global_equals_sum():
    cases = [
        _case("cal-rel-01", "relevancy", "pass"),
        _case("cal-rel-02", "relevancy", "fail"),
        _case("cal-fai-01", "faithfulness", "pass"),
        _case("cal-fai-02", "faithfulness", "fail"),
    ]
    verdicts = [_v(0.9), _v(0.5, parse_failed=True), _v(0.5, parse_failed=True), _v(0.1)]
    report = compute_calibration(cases, verdicts, judge="geval")

    for section in (report.global_, *report.per_criterion.values()):
        assert section.result.n_valid + section.n_parse_failed == section.n_cases
    summed = sum(s.n_parse_failed for s in report.per_criterion.values())
    assert report.global_.n_parse_failed == summed == report.n_parse_failed


def test_length_mismatch_raises():
    cases = [_case("cal-rel-01", "relevancy", "pass")]
    with pytest.raises(ValueError, match="align 1:1"):
        compute_calibration(cases, [], judge="geval")


# --- serialization ---------------------------------------------------------- #
def test_to_dict_is_json_safe_with_named_cells_and_null_kappa():
    cases = [_case("cal-rel-01", "relevancy", "pass"), _case("cal-rel-02", "relevancy", "pass")]
    verdicts = [_v(0.9), _v(0.9)]  # both human+judge all pass -> degenerate
    report = compute_calibration(cases, verdicts, judge="geval", threshold=0.5, created=123)
    payload = report.to_dict()
    text = json.dumps(payload)  # must not raise

    assert payload["judge"] == "geval" and payload["created"] == 123
    assert "global" in payload and "global_" not in payload
    assert set(payload["per_criterion"]) == {"relevancy", "faithfulness"}
    rel = payload["per_criterion"]["relevancy"]
    assert rel["confusion_matrix"]["orientation"] == "rows=human, cols=judge; positive='pass'"
    assert rel["confusion_matrix"]["human_pass_judge_pass"] == 2
    # degenerate relevancy slice -> kappa null (not NaN, not 1.0)
    assert rel["kappa"] is None
    assert '"kappa": null' in text
