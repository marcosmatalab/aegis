"""Pure red-team-gate baseline engine — offline, fixture-driven (no run, no key, no net).

Covers to_redteam_baseline reduction + every compare_redteam_to_baseline rule and edge:
the headline attack_now_passing anti-downgrade lock (incl. the reclassify-as-gap
scenario), detection_downgraded (block->redact), the informational block_code_changed,
the de-duplicated category_detection_drop, improvements-never-fail, and the exit-2
RedteamBaselineError guards (suite/mode mismatch, id-set drift, category remap, malformed).
The committed-baseline self-consistency lock lives in test_redteam_gate_cli-adjacent
checks here too (the fresh hermetic run == the committed contract).
"""

from __future__ import annotations

import copy
import json

import pytest

from aegis.redteam.baseline import (
    REDTEAM_MODE,
    REGRESSION_KINDS,
    RedteamBaselineError,
    compare_redteam_to_baseline,
    load_redteam_baseline,
    redteam_baseline_path,
    to_redteam_baseline,
)
from aegis.redteam.dataset import load_attacks
from aegis.redteam.models import AttackCase
from aegis.redteam.outcome import AttackResult
from aegis.redteam.report import build_report
from aegis.redteam.runner import build_redteam_settings, scan


def _baseline() -> dict:
    # two prompt_injection attacks (one blocked, one a by-design gap) + one redacted
    # pii_input, so every rule has something to bite on.
    return {
        "schema_version": 1,
        "suite": "redteam",
        "mode": "mock-offline",
        "rate_decimals": 6,
        "case_count": 3,
        "categories": {
            "prompt_injection": {
                "total": 2, "blocked": 1, "redacted": 0, "passed": 1,
                "caught": 1, "detection_rate": 0.5,
            },
            "pii_input": {
                "total": 1, "blocked": 0, "redacted": 1, "passed": 0,
                "caught": 1, "detection_rate": 1.0,
            },
        },
        "attacks": {
            "inj-block": {"category": "prompt_injection", "outcome": "blocked", "code": "prompt_injection"},  # noqa: E501
            "inj-gap": {"category": "prompt_injection", "outcome": "passed", "code": None},
            "pii-red": {"category": "pii_input", "outcome": "redacted", "code": None},
        },
    }  # fmt: skip


def _kinds(findings) -> set[str]:
    return {f.kind for f in findings}


# --- to_redteam_baseline reduction ------------------------------------------ #
def test_reducer_shape_and_excludes_catalog_authored_fields():
    cases = [
        AttackCase(
            id="a1", vector="input", category="prompt_injection", payload="x",
            expected_outcome="blocked", expected_code="prompt_injection",
        ),
        AttackCase(
            id="a2", vector="input", category="prompt_injection", payload="y",
            expected_outcome="passed", is_known_gap=True, gap_reason="documented blind spot",
        ),
    ]  # fmt: skip
    results = [
        AttackResult(cases[0], "blocked", "prompt_injection"),
        AttackResult(cases[1], "passed", None),
    ]
    report = build_report(results, suite="redteam", created=123)
    bl = to_redteam_baseline(report, results)

    assert bl["schema_version"] == 1 and bl["mode"] == REDTEAM_MODE and bl["rate_decimals"] == 6
    assert "created" not in bl and "overall_detection_rate" not in bl
    assert set(bl["attacks"]) == {"a1", "a2"}
    # per-attack rows carry OBSERVED outcome+code only — none of the catalog's authored
    # expected_outcome / is_known_gap / gap_reason / payload leak in.
    assert bl["attacks"]["a1"] == {
        "category": "prompt_injection",
        "outcome": "blocked",
        "code": "prompt_injection",
    }
    assert bl["attacks"]["a2"] == {
        "category": "prompt_injection",
        "outcome": "passed",
        "code": None,
    }
    cat = bl["categories"]["prompt_injection"]
    assert set(cat) == {"total", "blocked", "redacted", "passed", "caught", "detection_rate"}
    assert cat["caught"] == 1 and cat["detection_rate"] == 0.5  # 1 of 2 caught


# --- happy path ------------------------------------------------------------- #
def test_identical_has_no_findings():
    assert compare_redteam_to_baseline(_baseline(), copy.deepcopy(_baseline())) == []


# --- attack_now_passing: THE anti-downgrade lock ---------------------------- #
def test_caught_attack_now_passing_is_a_regression():
    cur = copy.deepcopy(_baseline())
    cur["attacks"]["inj-block"]["outcome"] = "passed"
    cur["attacks"]["inj-block"]["code"] = None
    cur["categories"]["prompt_injection"] = {
        "total": 2, "blocked": 0, "redacted": 0, "passed": 2, "caught": 0, "detection_rate": 0.0,
    }  # fmt: skip
    findings = compare_redteam_to_baseline(_baseline(), cur)
    assert "attack_now_passing" in _kinds(findings)
    f = next(f for f in findings if f.kind == "attack_now_passing")
    assert "inj-block prompt_injection" in f.scope
    assert f.kind in REGRESSION_KINDS  # blocks the merge


def test_reclassify_as_known_gap_cannot_suppress_the_regression():
    # the headline silent-downgrade: the catalog edit that relabels the now-passing
    # attack a known gap is IRRELEVANT — the gate reads only the baseline's frozen
    # caught state + the current observed outcome, never is_known_gap/expected_outcome.
    cur = copy.deepcopy(_baseline())
    cur["attacks"]["inj-block"]["outcome"] = "passed"
    cur["attacks"]["inj-block"]["code"] = None
    cur["categories"]["prompt_injection"] = {
        "total": 2, "blocked": 0, "redacted": 0, "passed": 2, "caught": 0, "detection_rate": 0.0,
    }  # fmt: skip
    # (no is_known_gap field exists in the baseline contract at all — by design)
    findings = compare_redteam_to_baseline(_baseline(), cur)
    assert any(f.kind == "attack_now_passing" and "inj-block" in f.scope for f in findings)


def test_known_gap_that_keeps_passing_is_a_noop():
    cur = copy.deepcopy(_baseline())  # inj-gap stays passed->passed
    assert compare_redteam_to_baseline(_baseline(), cur) == []


# --- detection_downgraded: block -> redact ---------------------------------- #
def test_block_downgraded_to_redact_is_a_regression():
    cur = copy.deepcopy(_baseline())
    cur["attacks"]["inj-block"]["outcome"] = "redacted"
    cur["attacks"]["inj-block"]["code"] = None
    cur["categories"]["prompt_injection"] = {
        "total": 2, "blocked": 0, "redacted": 1, "passed": 1, "caught": 1, "detection_rate": 0.5,
    }  # fmt: skip
    findings = compare_redteam_to_baseline(_baseline(), cur)
    assert _kinds(findings) == {"detection_downgraded"}
    assert "inj-block prompt_injection" in findings[0].scope
    assert findings[0].kind in REGRESSION_KINDS  # blocks the merge (exit 1)


def test_redact_upgraded_to_block_is_an_improvement():
    cur = copy.deepcopy(_baseline())
    cur["attacks"]["pii-red"]["outcome"] = "blocked"
    cur["attacks"]["pii-red"]["code"] = "pii_leak"
    cur["categories"]["pii_input"] = {
        "total": 1, "blocked": 1, "redacted": 0, "passed": 0, "caught": 1, "detection_rate": 1.0,
    }  # fmt: skip
    assert compare_redteam_to_baseline(_baseline(), cur) == []


# --- block_code_changed: informational, never blocks ------------------------ #
def test_block_code_change_is_informational_not_a_regression():
    cur = copy.deepcopy(_baseline())
    cur["attacks"]["inj-block"]["code"] = "policy_denied"  # still blocked, different code
    findings = compare_redteam_to_baseline(_baseline(), cur)
    assert _kinds(findings) == {"block_code_changed"}
    assert findings[0].kind not in REGRESSION_KINDS  # exit 0


# --- improvements never fail ------------------------------------------------ #
def test_gap_now_caught_is_an_improvement():
    cur = copy.deepcopy(_baseline())
    cur["attacks"]["inj-gap"]["outcome"] = "blocked"
    cur["attacks"]["inj-gap"]["code"] = "prompt_injection"
    cur["categories"]["prompt_injection"] = {
        "total": 2, "blocked": 2, "redacted": 0, "passed": 0, "caught": 2, "detection_rate": 1.0,
    }  # fmt: skip
    assert compare_redteam_to_baseline(_baseline(), cur) == []


# --- category_detection_drop + de-duplication ------------------------------- #
def test_category_drop_is_deduplicated_when_explained_by_a_per_attack_finding():
    # inj-block flips caught->passed: the per-attack rule fires AND the category rate
    # drops 0.5->0.0; the aggregate must be SUPPRESSED so one root cause prints once.
    cur = copy.deepcopy(_baseline())
    cur["attacks"]["inj-block"]["outcome"] = "passed"
    cur["attacks"]["inj-block"]["code"] = None
    cur["categories"]["prompt_injection"] = {
        "total": 2, "blocked": 0, "redacted": 0, "passed": 2, "caught": 0, "detection_rate": 0.0,
    }  # fmt: skip
    findings = compare_redteam_to_baseline(_baseline(), cur)
    assert _kinds(findings) == {"attack_now_passing"}  # NOT also category_detection_drop


def test_diffuse_category_drop_with_no_per_attack_cause_still_fires():
    # a category rate drop NOT explained by any per-attack finding (e.g. a reducer bug
    # or diffuse erosion): the aggregate net catches it.
    cur = copy.deepcopy(_baseline())
    cur["categories"]["pii_input"]["detection_rate"] = 0.4  # was 1.0, no per-attack change
    findings = compare_redteam_to_baseline(_baseline(), cur)
    assert _kinds(findings) == {"category_detection_drop"}
    assert "pii_input" in findings[0].scope
    assert findings[0].kind in REGRESSION_KINDS  # blocks the merge (exit 1)


def test_tolerance_band_absorbs_a_tiny_drop():
    cur = copy.deepcopy(_baseline())
    cur["categories"]["pii_input"]["detection_rate"] = 0.999
    assert compare_redteam_to_baseline(_baseline(), cur, tolerance=0.005) == []


# --- exit-2 guards (RedteamBaselineError) ----------------------------------- #
def test_suite_mismatch_raises():
    cur = copy.deepcopy(_baseline())
    cur["suite"] = "other"
    with pytest.raises(RedteamBaselineError, match="suite"):
        compare_redteam_to_baseline(_baseline(), cur)


def test_mode_mismatch_raises_latent_tripwire():
    cur = copy.deepcopy(_baseline())
    cur["mode"] = "real-pipeline"
    with pytest.raises(RedteamBaselineError, match="hermetic offline pipeline"):
        compare_redteam_to_baseline(_baseline(), cur)


def test_id_set_drift_raises_regenerate():
    cur = copy.deepcopy(_baseline())
    cur["attacks"]["inj-new"] = {"category": "prompt_injection", "outcome": "passed", "code": None}
    with pytest.raises(RedteamBaselineError, match="attack-set changed"):
        compare_redteam_to_baseline(_baseline(), cur)


def test_category_remap_raises():
    cur = copy.deepcopy(_baseline())
    cur["attacks"]["inj-block"]["category"] = "policy_denylist"
    with pytest.raises(RedteamBaselineError, match="category"):
        compare_redteam_to_baseline(_baseline(), cur)


def test_malformed_category_caught_mismatch_raises():
    bad = _baseline()
    bad["categories"]["prompt_injection"]["caught"] = 2  # != blocked+redacted (1)
    with pytest.raises(RedteamBaselineError, match="caught != blocked"):
        compare_redteam_to_baseline(bad, _baseline())


def test_malformed_attack_code_without_block_raises():
    bad = _baseline()
    bad["attacks"]["pii-red"]["code"] = "pii_leak"  # redacted must carry code=None
    with pytest.raises(RedteamBaselineError, match="iff outcome=='blocked'"):
        compare_redteam_to_baseline(bad, _baseline())


def test_load_missing_baseline_raises(tmp_path):
    with pytest.raises(RedteamBaselineError, match="not found"):
        load_redteam_baseline(tmp_path / "nope.json")


def test_baseline_detection_rate_lie_raises():
    # the baseline rate is the trusted FLOOR _category_regressions compares against, so a
    # fabricated (deflated/inflated) rate must be rejected, not trusted.
    bad = _baseline()
    bad["categories"]["pii_input"]["detection_rate"] = 0.1  # caught/total actually = 1.0
    with pytest.raises(RedteamBaselineError, match="detection_rate != caught/total"):
        compare_redteam_to_baseline(bad, _baseline())


def test_phantom_category_in_baseline_raises():
    bad = _baseline()
    bad["categories"]["ghost"] = {
        "total": 0, "blocked": 0, "redacted": 0, "passed": 0, "caught": 0, "detection_rate": 0.0,
    }  # fmt: skip
    with pytest.raises(RedteamBaselineError, match="category set"):
        compare_redteam_to_baseline(bad, _baseline())


def test_current_missing_suite_is_clean_exit_2_not_keyerror():
    # current["suite"] is read with .get, so a malformed current is the typed exit-2 path
    # rather than a raw KeyError the CLI would not catch.
    cur = copy.deepcopy(_baseline())
    del cur["suite"]
    with pytest.raises(RedteamBaselineError, match="suite"):
        compare_redteam_to_baseline(_baseline(), cur)


def test_malformed_current_structure_raises():
    # the PURE comparator validates current's STRUCTURE too (not its rate): a hand-built
    # current with a redacted row carrying a code is the clean exit-2 path.
    cur = copy.deepcopy(_baseline())
    cur["attacks"]["pii-red"]["code"] = "pii_leak"  # redacted must carry code=None
    with pytest.raises(RedteamBaselineError, match="iff outcome=='blocked'"):
        compare_redteam_to_baseline(_baseline(), cur)


def test_regression_kinds_lock():
    # a one-token edit to REGRESSION_KINDS would silently demote a HARD rule to an
    # informational note (exit 0); pin the exact set so any membership change trips a test.
    expected = {
        "attack_now_passing",
        "detection_downgraded",
        "category_detection_drop",
        "category_dropped",
    }
    assert set(REGRESSION_KINDS) == expected


# --- the committed red-team baseline (the gate contract) -------------------- #
def _fresh_redteam_baseline() -> dict:
    results = scan(load_attacks())
    report = build_report(results, suite="redteam", created=0)
    return to_redteam_baseline(report, results)


def test_committed_redteam_baseline_matches_fresh_hermetic_run():
    # the anti-drift LOCK: the committed contract must equal a fresh hermetic run
    # EXACTLY, so any guardrail/catalog change without --update-baseline fails here
    # (locally, before CI) and forces a reviewed re-baseline in the same PR.
    assert load_redteam_baseline(redteam_baseline_path("redteam")) == _fresh_redteam_baseline()


def test_committed_redteam_baseline_well_formed():
    bl = load_redteam_baseline(redteam_baseline_path("redteam"))
    assert bl["schema_version"] == 1 and bl["mode"] == "mock-offline" and bl["rate_decimals"] == 6
    ids = {c.id for c in load_attacks()}
    assert bl["case_count"] == len(ids) == 25
    assert set(bl["attacks"]) == ids
    for atk in bl["attacks"].values():
        assert set(atk) == {"category", "outcome", "code"}
        assert atk["outcome"] in ("blocked", "redacted", "passed")
        assert (atk["code"] is not None) == (atk["outcome"] == "blocked")
    for stat in bl["categories"].values():
        assert set(stat) == {"total", "blocked", "redacted", "passed", "caught", "detection_rate"}
        assert 0.0 <= stat["detection_rate"] <= 1.0
        assert stat["caught"] == stat["blocked"] + stat["redacted"]
    # the 7 named gaps are observed as passing — surfaced, never padded away
    passed = [a for a in bl["attacks"].values() if a["outcome"] == "passed"]
    assert len(passed) == 7


def test_committed_baseline_is_byte_idempotent(tmp_path):
    from aegis.evals.persistence import write_baseline

    a, b = tmp_path / "a.json", tmp_path / "b.json"
    write_baseline(_fresh_redteam_baseline(), a)
    write_baseline(_fresh_redteam_baseline(), b)
    assert a.read_text(encoding="utf-8") == b.read_text(encoding="utf-8")


def test_committed_baseline_file_is_canonical():
    # the committed file on disk must be the exact canonical write (sorted keys, indent 2,
    # trailing newline) a fresh --update-baseline produces, so a semantics-preserving
    # hand-edit (reordered keys / reflow) can't cause a spurious future diff. Newlines are
    # normalized so the byte-lock survives git's eol handling across platforms.
    committed = redteam_baseline_path("redteam").read_text(encoding="utf-8").replace("\r\n", "\n")
    canonical = (
        json.dumps(_fresh_redteam_baseline(), indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    assert committed == canonical


def test_reclassify_as_gap_through_the_reducer_still_flags():
    # end-to-end via the REAL reducer: an attack the catalog now marks is_known_gap=True
    # (observed passing) but that the baseline recorded as caught -> attack_now_passing
    # still fires, and the reduced row never carries is_known_gap (the label can't leak).
    case = AttackCase(
        id="a-gap", vector="input", category="prompt_injection", payload="x",
        expected_outcome="passed", is_known_gap=True, gap_reason="now a documented gap",
    )  # fmt: skip
    now = [AttackResult(case, "passed", None)]
    was = [AttackResult(case, "blocked", "prompt_injection")]
    current = to_redteam_baseline(build_report(now), now)
    baseline = to_redteam_baseline(build_report(was), was)
    findings = compare_redteam_to_baseline(baseline, current)
    assert [f.kind for f in findings] == ["attack_now_passing"]
    assert "is_known_gap" not in current["attacks"]["a-gap"]  # catalog label never leaks in


def test_baseline_is_hermetic_under_hostile_env(monkeypatch):
    # behaviour-FLIPPING env vars (disable guardrails, swap PII engine, drop the
    # toxicity threshold) must NOT change a single reduced value — build_redteam_settings
    # pins every field as an init kwarg, so the gate's input is deterministic.
    committed = load_redteam_baseline(redteam_baseline_path("redteam"))
    monkeypatch.setenv("AEGIS_GUARDRAILS_ENABLED", "false")
    monkeypatch.setenv("AEGIS_GR_PII_ENGINE", "presidio")
    monkeypatch.setenv("AEGIS_GR_TOXICITY_THRESHOLD", "0.01")
    monkeypatch.setenv("AEGIS_GR_INJECTION_ENABLED", "false")
    assert build_redteam_settings().gr_pii_engine == "regex"  # env ignored (init kwargs win)
    assert _fresh_redteam_baseline() == committed  # full reduced dict unchanged
