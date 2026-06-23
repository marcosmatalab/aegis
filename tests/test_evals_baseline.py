"""Pure eval-gate baseline engine — offline, fixture-driven (no run, no key, no net).

Covers to_baseline reduction + every compare_to_baseline rule and edge: per-level
mean drop, the per-case score-drop rule (closes the sub-threshold L2 erosion hole),
per-case pass->fail, L2 applicability loss, the latent NEW-parse_failed tripwire
(exercised only here, via the pure comparator — it is unreachable under the mock),
improvements, and the exit-2 BaselineError guards (judge mismatch, id-set drift).
"""

from __future__ import annotations

import copy

import pytest

from aegis.evals.baseline import (
    BaselineError,
    Regression,
    baseline_path,
    compare_to_baseline,
    load_baseline,
    to_baseline,
)
from aegis.evals.dataset import load_golden
from aegis.evals.judge.agent import MockTrajectoryJudge
from aegis.evals.judge.mock import MockJudge
from aegis.evals.persistence import write_baseline
from aegis.evals.runner import run_suite


def _baseline() -> dict:
    return {
        "schema_version": 1,
        "suite": "golden",
        "judge": "mock",
        "case_count": 2,
        "score_decimals": 6,
        "levels": {
            "L1": {"mean_score": 0.9, "passed": 2, "scored": 2},
            "L2": {"mean_score": 0.8, "passed": 1, "scored": 1},
            "L3": {"mean_score": 1.0, "passed": 2, "scored": 2},
        },
        "overall_score": 0.9,
        "cases": {
            "case-a": {
                "l1_passed": True, "l1_score": 1.0,
                "l2_applicable": True, "l2_passed": True, "l2_score": 0.8,
                "l2_parse_failed": False,
                "l3_passed": True, "l3_score": 1.0,
            },
            "case-b": {
                "l1_passed": True, "l1_score": 0.8,
                "l2_applicable": False, "l2_passed": False, "l2_score": 0.0,
                "l2_parse_failed": False,
                "l3_passed": True, "l3_score": 1.0,
            },
        },
    }  # fmt: skip


def _kinds(regs: list[Regression]) -> set[str]:
    return {r.kind for r in regs}


# --- to_baseline reduction -------------------------------------------------- #
def test_to_baseline_extracts_contract_and_excludes_noise():
    report = {
        "suite": "golden", "judge": "mock", "case_count": 1, "created": 123,
        "overall_score": 0.9,
        "levels": {"L1": {"level": "L1", "mean_score": 0.9, "passed": 1, "scored": 1}},
        "clear": {"cost": {"x": 1}}, "trajectory": {"t": 1},
        "cases": [
            {
                "id": "x", "tags": ["t"],
                "l1": {"score": 1.0, "passed": True, "reasons": [], "breakdown": {}},
                "l2": {
                    "score": 0.5, "passed": True, "reasons": [],
                    "breakdown": {"applicable": True, "faithfulness_parse_failed": True},
                },
                "l3": {"score": 1.0, "passed": True, "reasons": [], "breakdown": {}},
                "trajectory": {}, "agent_judge": {},
            }
        ],
    }  # fmt: skip
    bl = to_baseline(report)
    assert bl["schema_version"] == 1 and bl["score_decimals"] == 6
    assert "created" not in bl and "clear" not in bl and "trajectory" not in bl
    assert set(bl["levels"]) == {"L1"} and bl["levels"]["L1"] == {
        "mean_score": 0.9,
        "passed": 1,
        "scored": 1,
    }
    x = bl["cases"]["x"]
    assert x["l1_score"] == 1.0 and x["l2_score"] == 0.5 and x["l2_applicable"] is True
    assert x["l2_parse_failed"] is True  # presence-derived from the *_parse_failed key
    assert "reasons" not in x and "breakdown" not in x


# --- happy path ------------------------------------------------------------- #
def test_identical_has_no_regressions():
    bl = _baseline()
    assert compare_to_baseline(bl, copy.deepcopy(bl)) == []


# --- per-level mean drop ---------------------------------------------------- #
def test_level_mean_drop_beyond_tolerance_flags_level():
    cur = copy.deepcopy(_baseline())
    cur["levels"]["L2"]["mean_score"] = 0.79  # drop 0.01 > tol 0.005
    regs = compare_to_baseline(_baseline(), cur)
    assert _kinds(regs) == {"level_mean_drop"}
    assert "L2" in str(regs[0])


def test_level_mean_drop_within_tolerance_passes():
    cur = copy.deepcopy(_baseline())
    cur["levels"]["L2"]["mean_score"] = 0.796  # drop 0.004 < tol 0.005
    assert compare_to_baseline(_baseline(), cur) == []


def test_level_disappeared_flags():
    cur = copy.deepcopy(_baseline())
    del cur["levels"]["L2"]
    assert _kinds(compare_to_baseline(_baseline(), cur)) == {"level_dropped"}


# --- per-case score drop (closes the sub-threshold L2 erosion hole) --------- #
def test_per_case_l2_score_erosion_without_flip_or_mean_move_is_caught():
    # the finding-2 scenario: an applicable L2 case erodes but stays "passing" and
    # the level mean is untouched -> still a regression via the per-case score rule
    cur = copy.deepcopy(_baseline())
    cur["cases"]["case-a"]["l2_score"] = 0.51  # was 0.8; l2_passed stays True, L2 mean unchanged
    regs = compare_to_baseline(_baseline(), cur)
    assert _kinds(regs) == {"case_score_drop"}
    assert "case-a L2" in str(regs[0])


def test_per_case_l1_score_drop_is_caught():
    cur = copy.deepcopy(_baseline())
    cur["cases"]["case-b"]["l1_score"] = 0.6  # was 0.8
    assert any(
        r.kind == "case_score_drop" and "case-b L1" in r.scope
        for r in compare_to_baseline(_baseline(), cur)
    )


# --- per-case pass->fail ---------------------------------------------------- #
def test_per_case_pass_to_fail_flagged_per_level():
    cur = copy.deepcopy(_baseline())
    cur["cases"]["case-a"]["l3_passed"] = False  # score unchanged -> only a flip
    regs = compare_to_baseline(_baseline(), cur)
    assert _kinds(regs) == {"case_pass_fail"}
    assert "case-a L3" in str(regs[0])


def test_l2_pass_fail_only_when_applicable():
    cur = copy.deepcopy(_baseline())
    # case-b is NOT L2-applicable in the baseline -> an l2_passed change is ignored
    cur["cases"]["case-b"]["l2_passed"] = True
    assert compare_to_baseline(_baseline(), cur) == []


# --- L2 applicability loss -------------------------------------------------- #
def test_l2_applicability_loss_flagged():
    cur = copy.deepcopy(_baseline())
    cur["cases"]["case-a"]["l2_applicable"] = False
    assert _kinds(compare_to_baseline(_baseline(), cur)) == {"l2_dropped"}


# --- NEW parse_failed (latent tripwire — only reachable via the pure comparator) #
def test_new_parse_failed_is_hard_fail_even_with_unchanged_score():
    cur = copy.deepcopy(_baseline())
    cur["cases"]["case-a"]["l2_parse_failed"] = True  # nothing else changes
    regs = compare_to_baseline(_baseline(), cur)
    assert _kinds(regs) == {"new_parse_failed"}
    assert "case-a L2" in str(regs[0])


# --- improvements never fail ------------------------------------------------ #
def test_improvements_do_not_fail():
    cur = copy.deepcopy(_baseline())
    cur["levels"]["L1"]["mean_score"] = 1.0  # up
    cur["cases"]["case-a"]["l2_score"] = 0.95  # up
    cur["cases"]["case-b"]["l3_passed"] = True  # already true; a fail->pass elsewhere is also fine
    cur["cases"]["case-b"]["l1_score"] = 0.95  # up
    assert compare_to_baseline(_baseline(), cur) == []


# --- exit-2 guards (BaselineError) ------------------------------------------ #
def test_judge_mismatch_raises():
    cur = copy.deepcopy(_baseline())
    cur["judge"] = "geval"
    with pytest.raises(BaselineError, match="only compares the deterministic mock"):
        compare_to_baseline(_baseline(), cur)


def test_id_set_drift_raises_regenerate():
    cur = copy.deepcopy(_baseline())
    cur["cases"]["case-c"] = cur["cases"]["case-a"]
    with pytest.raises(BaselineError, match="case-set changed"):
        compare_to_baseline(_baseline(), cur)


# --- load_baseline + round-trip --------------------------------------------- #
def test_load_missing_baseline_raises(tmp_path):
    with pytest.raises(BaselineError, match="not found"):
        load_baseline(tmp_path / "nope.json")


def test_load_bad_schema_version_raises(tmp_path):
    p = tmp_path / "b.json"
    bad = _baseline()
    bad["schema_version"] = 999
    write_baseline(bad, p)
    with pytest.raises(BaselineError, match="schema_version"):
        load_baseline(p)


def test_load_missing_top_level_key_raises_malformed(tmp_path):
    p = tmp_path / "b.json"
    bad = _baseline()
    del bad["levels"]
    write_baseline(bad, p)
    with pytest.raises(BaselineError, match="malformed"):
        load_baseline(p)


def test_compare_malformed_baseline_case_raises_not_keyerror():
    # a hand-corrupted committed baseline (a dropped per-case key) must be a clean
    # BaselineError (-> exit 2), never a raw KeyError + traceback
    bad = _baseline()
    del bad["cases"]["case-a"]["l2_applicable"]
    with pytest.raises(BaselineError, match="malformed"):
        compare_to_baseline(bad, _baseline())


def test_compare_malformed_baseline_level_raises():
    bad = _baseline()
    del bad["levels"]["L1"]["mean_score"]
    with pytest.raises(BaselineError, match="malformed"):
        compare_to_baseline(bad, _baseline())


def test_write_then_load_round_trips(tmp_path):
    p = tmp_path / "b.json"
    write_baseline(_baseline(), p)
    assert load_baseline(p) == _baseline()
    assert p.read_text(encoding="utf-8").endswith("\n")  # trailing newline


# --- the committed golden baseline (the gate contract) ---------------------- #
def _fresh_golden_baseline() -> dict:
    report = run_suite(load_golden(), MockJudge(), MockTrajectoryJudge(), suite="golden", created=0)
    return to_baseline(report)


def test_committed_golden_baseline_matches_fresh_mock_run():
    # the anti-drift LOCK: the committed contract must equal a fresh deterministic
    # mock run EXACTLY, so any scoring/golden change without --update-baseline fails
    # here (locally, before CI) and forces a reviewed re-baseline in the same PR.
    assert load_baseline(baseline_path("golden")) == _fresh_golden_baseline()


def test_committed_golden_baseline_well_formed():
    bl = load_baseline(baseline_path("golden"))
    assert bl["schema_version"] == 1 and bl["judge"] == "mock" and bl["score_decimals"] == 6
    golden_ids = {c.id for c in load_golden()}
    assert bl["case_count"] == len(golden_ids)
    assert set(bl["cases"]) == golden_ids
    assert set(bl["levels"]) <= {"L1", "L2", "L3"}
    assert 0.0 <= bl["overall_score"] <= 1.0
