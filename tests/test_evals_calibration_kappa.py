"""Pure Cohen's kappa core — offline, no judge, no key, no network.

Covers the formula against a hand-computed value, the two degenerate paths
(both-one-class and empty), the load-bearing human-constant/judge-split case
(kappa is well defined, NOT undefined), the 0.5 binarization boundary, matrix
orientation, and the Landis-Koch band table.
"""

from __future__ import annotations

import json

import pytest

from aegis.evals.calibration.kappa import (
    ConfusionMatrix,
    binarize,
    build_matrix,
    cohen_kappa,
    kappa_from_pairs,
    landis_koch_band,
)


# --- the formula, pinned against a fully worked example --------------------- #
def test_hand_computed_kappa():
    # tp=6, fn=2, fp=3, tn=9, n=20.
    # p_o = (6+9)/20 = 0.75
    # human_pass=8/20=0.40, human_fail=0.60, judge_pass=9/20=0.45, judge_fail=0.55
    # p_e = 0.40*0.45 + 0.60*0.55 = 0.18 + 0.33 = 0.51
    # kappa = (0.75 - 0.51) / (1 - 0.51) = 0.24 / 0.49 = 0.4897959183673469
    result = cohen_kappa(ConfusionMatrix(tp=6, fn=2, fp=3, tn=9))
    assert result.p_o == 0.75
    assert result.p_e == pytest.approx(0.51)
    assert result.kappa == pytest.approx(0.4897959183673469)
    assert result.n_valid == 20
    assert result.band == "moderate"


def test_perfect_agreement_is_one():
    result = cohen_kappa(ConfusionMatrix(tp=10, fn=0, fp=0, tn=10))
    assert result.p_o == 1.0
    assert result.kappa == pytest.approx(1.0)
    assert result.band == "almost perfect"


def test_chance_level_agreement_is_zero():
    # p_o == p_e == 0.5 -> kappa 0.0
    result = cohen_kappa(ConfusionMatrix(tp=5, fn=5, fp=5, tn=5))
    assert result.kappa == pytest.approx(0.0)
    assert result.band == "slight"  # [0, 0.20) per the convention


def test_worse_than_chance_is_negative():
    result = cohen_kappa(ConfusionMatrix(tp=0, fn=10, fp=10, tn=0))
    assert result.kappa == pytest.approx(-1.0)
    assert result.band == "poor"


# --- the load-bearing distinction the critic caught ------------------------- #
def test_human_constant_judge_split_is_well_defined_not_degenerate():
    # human labeled every case 'pass' (constant), judge split 5/5.
    # tp=5, fn=5, fp=0, tn=0. Only the HUMAN marginal saturates (1.0/0.0); the
    # judge marginal is 0.5/0.5, so 1 - p_e = 0.5 > 0 and kappa is DEFINED (0.0).
    result = cohen_kappa(ConfusionMatrix(tp=5, fn=5, fp=0, tn=0))
    assert result.kappa is not None
    assert result.kappa == pytest.approx(0.0)
    assert result.band == "slight"


# --- degenerate paths: never raise, never fabricate ------------------------- #
def test_both_all_pass_is_undefined_keeps_p_o():
    result = cohen_kappa(ConfusionMatrix(tp=10, fn=0, fp=0, tn=0))
    assert result.kappa is None
    assert result.p_o == 1.0  # real observed agreement is still reported
    assert result.p_e == 1.0
    assert result.band == "undefined"


def test_both_all_fail_is_undefined_keeps_p_o():
    result = cohen_kappa(ConfusionMatrix(tp=0, fn=0, fp=0, tn=10))
    assert result.kappa is None
    assert result.p_o == 1.0
    assert result.p_e == 1.0
    assert result.band == "undefined"


def test_empty_matrix_is_all_none_no_zero_division():
    result = cohen_kappa(ConfusionMatrix())
    assert result.kappa is None
    assert result.p_o is None  # nothing to agree on — NOT a fabricated 0.0
    assert result.p_e is None
    assert result.n_valid == 0
    assert result.band == "undefined"


# --- binarization boundary -------------------------------------------------- #
@pytest.mark.parametrize(
    "score,expected",
    [(0.0, "fail"), (0.4999, "fail"), (0.5, "pass"), (0.5000001, "pass"), (1.0, "pass")],
)
def test_binarize_boundary(score, expected):
    assert binarize(score) == expected


def test_binarize_custom_threshold():
    assert binarize(0.3, threshold=0.3) == "pass"
    assert binarize(0.29, threshold=0.3) == "fail"


# --- matrix orientation (kappa is symmetric, so this must be pinned) --------- #
def test_build_matrix_orientation():
    # human fail & judge pass -> fp (judge over-passes)
    assert build_matrix([("fail", "pass")]).fp == 1
    # human pass & judge fail -> fn (judge over-fails)
    assert build_matrix([("pass", "fail")]).fn == 1
    m = build_matrix([("pass", "pass"), ("pass", "fail"), ("fail", "pass"), ("fail", "fail")])
    assert (m.tp, m.fn, m.fp, m.tn) == (1, 1, 1, 1)
    cells = m.to_dict()
    assert cells["orientation"] == "rows=human, cols=judge; positive='pass'"
    assert cells["human_fail_judge_pass"] == 1


def test_kappa_from_pairs_matches_compose():
    pairs = [("pass", "pass")] * 6 + [("pass", "fail")] * 2
    pairs += [("fail", "pass")] * 3 + [("fail", "fail")] * 9
    assert kappa_from_pairs(pairs).kappa == pytest.approx(0.4897959183673469)


# --- Landis-Koch bands ------------------------------------------------------ #
@pytest.mark.parametrize(
    "kappa,band",
    [
        (-0.1, "poor"),
        (0.0, "slight"),
        (0.19, "slight"),
        (0.20, "fair"),
        (0.40, "moderate"),
        (0.60, "substantial"),
        (0.80, "almost perfect"),
        (1.0, "almost perfect"),
        (None, "undefined"),
    ],
)
def test_landis_koch_bands(kappa, band):
    assert landis_koch_band(kappa) == band


# --- JSON-safety (null, never NaN) ------------------------------------------ #
def test_to_dict_serializes_degenerate_as_null():
    payload = cohen_kappa(ConfusionMatrix(tp=10, fn=0, fp=0, tn=0)).to_dict()
    text = json.dumps(payload)  # must not raise (None -> null; NaN would fail)
    assert '"kappa": null' in text
    assert payload["confusion_matrix"]["human_pass_judge_pass"] == 10
