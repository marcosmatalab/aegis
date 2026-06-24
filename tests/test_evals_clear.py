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
    latency_source="synthetic",
    cost_source="synthetic",
):
    return CaseSignal(
        l1,
        l3,
        l2_applicable,
        l2_passed,
        exact,
        actual,
        latency_ms,
        cost_usd,
        latency_source,
        cost_source,
    )


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


def test_synthetic_basis_discloses_traced_denominator():
    # only 1 of 3 cases carries a trace -> the basis must reveal the partial coverage
    clear = compute_clear(
        [_sig(cost_usd=0.02), _sig(), _sig()],
        overall_score=1.0,
    )
    assert "1/3 traced cases" in clear["cost"].basis


# --- cost / latency MEASURED + ESTIMATED (real telemetry via the bridge) ----- #
def test_latency_is_measured_when_all_real():
    clear = compute_clear(
        [_sig(latency_ms=120.0, latency_source="measured")],
        overall_score=1.0,
    )
    assert clear["latency"].status == "measured"
    assert clear["latency"].value == 120.0
    assert "MEASURED" in clear["latency"].basis


def test_cost_is_estimated_not_measured_when_all_real():
    # real measured tokens x static list price is an ESTIMATE, never 'measured'
    clear = compute_clear(
        [_sig(cost_usd=0.012, cost_source="estimated")],
        overall_score=1.0,
    )
    assert clear["cost"].status == "estimated"
    assert "static list price" in clear["cost"].basis


def test_mixed_provenance_downgrades_to_synthetic_with_disclosure():
    # one real-telemetry latency + one hand-authored -> the whole dim is synthetic,
    # and the basis must show the split (a single real case can't launder the suite)
    clear = compute_clear(
        [
            _sig(latency_ms=100.0, latency_source="measured"),
            _sig(latency_ms=300.0, latency_source="synthetic"),
        ],
        overall_score=1.0,
    )
    assert clear["latency"].status == "synthetic"
    assert clear["latency"].value == 200.0
    assert "1 from real telemetry, 1 hand-authored" in clear["latency"].basis


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


def test_zero_budget_falls_back_to_no_score_no_zero_division():
    # 0.0 is an allowed configured budget (ge=0.0) -> guard returns None, no ZeroDivisionError
    clear = compute_clear(
        [_sig(latency_ms=100.0, cost_usd=0.05)],
        overall_score=1.0,
        latency_budget_ms=0.0,
        cost_budget_usd=0.0,
    )
    assert clear["latency"].score is None
    assert clear["cost"].score is None


# --- empty suite ------------------------------------------------------------ #
def test_empty_suite_reliability_and_efficiency_not_applicable():
    clear = compute_clear([], overall_score=0.0)
    assert clear["reliability"].applicable is False
    assert clear["reliability"].score is None
    assert clear["efficiency"].applicable is False
    assert clear["cost"].status == "placeholder"
