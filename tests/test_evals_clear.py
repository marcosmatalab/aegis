"""Tests for the CLEAR framework dimensions (deterministic, offline)."""

from __future__ import annotations

from aegis.evals.clear import CaseSignal, compute_clear


def _sig(
    *,
    l1=True,
    l3=True,
    l2_applicable=False,
    l2_passed=False,
    exact=0,
    actual=0,
    latency_ms=None,
    cost_usd=None,
):
    return CaseSignal(l1, l3, l2_applicable, l2_passed, exact, actual, latency_ms, cost_usd)


# --- order + accuracy ------------------------------------------------------- #
def test_clear_returns_five_dimensions_in_order():
    clear = compute_clear([_sig()], overall_score=0.9)
    assert list(clear) == ["cost", "latency", "efficiency", "accuracy", "reliability"]


def test_accuracy_is_overall_score_and_measured():
    acc = compute_clear([_sig()], overall_score=0.83)["accuracy"]
    assert acc.status == "measured"
    assert acc.score == 0.83 and acc.value == 0.83 and acc.unit == "ratio"


# --- efficiency ------------------------------------------------------------- #
def test_efficiency_is_mean_useful_call_fraction():
    # case A: 2/2 useful = 1.0 ; case B: 1/2 = 0.5 -> mean 0.75
    clear = compute_clear([_sig(exact=2, actual=2), _sig(exact=1, actual=2)], overall_score=0.0)
    assert clear["efficiency"].status == "measured"
    assert clear["efficiency"].score == 0.75


def test_efficiency_not_applicable_without_tool_calls():
    eff = compute_clear([_sig(actual=0), _sig(actual=0)], overall_score=1.0)["efficiency"]
    assert eff.applicable is False
    assert eff.score is None


# --- reliability ------------------------------------------------------------ #
def test_reliability_end_to_end_success_rate():
    # one fully-passing case, one failing L3 -> 0.5
    clear = compute_clear([_sig(l1=True, l3=True), _sig(l1=True, l3=False)], overall_score=0.0)
    assert clear["reliability"].score == 0.5


def test_reliability_counts_applicable_l2_failure_as_unreliable():
    # L1+L3 pass but applicable L2 fails -> not end-to-end reliable
    clear = compute_clear(
        [_sig(l1=True, l3=True, l2_applicable=True, l2_passed=False)], overall_score=0.0
    )
    assert clear["reliability"].score == 0.0


def test_reliability_ignores_non_applicable_l2():
    clear = compute_clear(
        [_sig(l1=True, l3=True, l2_applicable=False, l2_passed=False)], overall_score=0.0
    )
    assert clear["reliability"].score == 1.0


# --- cost / latency honesty (synthetic vs placeholder) ---------------------- #
def test_cost_and_latency_are_placeholder_without_trace():
    clear = compute_clear([_sig()], overall_score=1.0)
    for name in ("cost", "latency"):
        dim = clear[name]
        assert dim.status == "placeholder"
        assert dim.applicable is False
        assert dim.value is None and dim.score is None


def test_cost_and_latency_are_synthetic_with_trace_and_no_score_without_budget():
    clear = compute_clear(
        [_sig(cost_usd=0.02, latency_ms=100.0), _sig(cost_usd=0.04, latency_ms=300.0)],
        overall_score=1.0,
    )
    assert clear["cost"].status == "synthetic"
    assert clear["cost"].value == 0.03 and clear["cost"].unit == "usd"
    assert clear["cost"].score is None  # no budget configured
    assert clear["latency"].status == "synthetic"
    assert clear["latency"].value == 200.0 and clear["latency"].unit == "ms"


def test_budget_normalizes_to_score_lower_is_better():
    clear = compute_clear(
        [_sig(latency_ms=250.0, cost_usd=0.05)],
        overall_score=1.0,
        latency_budget_ms=1000.0,
        cost_budget_usd=0.10,
    )
    # 1 - 250/1000 = 0.75 ; 1 - 0.05/0.10 = 0.5
    assert clear["latency"].score == 0.75
    assert clear["cost"].score == 0.5


def test_budget_clamps_to_zero_when_over_budget():
    clear = compute_clear([_sig(latency_ms=2000.0)], overall_score=1.0, latency_budget_ms=1000.0)
    assert clear["latency"].score == 0.0
