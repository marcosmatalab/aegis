"""CLEAR framework — five per-run dimensions: Cost, Latency, Efficiency,
Accuracy, Reliability.

HONESTY (kept explicit in the report via each dimension's ``status``):

* **Accuracy / Efficiency / Reliability** are ``measured`` — computed
  deterministically from data Aegis already has (eval scores and the recorded
  trajectory).
* **Latency** is ``measured`` when it comes from a real request span (F1.x OTel
  bridge): the span's wall-clock duration is a genuine measurement.
* **Cost** is ``estimated`` when it comes from real measured tokens multiplied by a
  STATIC list price — the tokens are measured, the price is an assumed constant, so
  the dollar figure is an estimate, NOT a measurement (a deliberately distinct
  status from ``measured``).
* **Cost / Latency** are ``synthetic`` when the value is a hand-authored ``trace``
  number, and ``placeholder`` when there is no telemetry at all. The committed mock
  suite has no real telemetry, so it stays placeholder/synthetic — never measured/
  estimated. Provenance is HOMOGENEOUS per dimension: a single hand-authored value
  among real ones downgrades the whole dimension to ``synthetic``.

Each dimension is a normalized ``score`` in 0..1 where that is meaningful, plus a
raw ``value`` + ``unit``. Cost/Latency only get a normalized score when an
optional budget/SLO is configured (otherwise the raw value stands alone).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Status = Literal["measured", "estimated", "synthetic", "placeholder"]


@dataclass(frozen=True, slots=True)
class CaseSignal:
    """The per-case inputs CLEAR needs, assembled by the runner."""

    l1_passed: bool
    l3_passed: bool
    l2_applicable: bool
    l2_passed: bool
    exact_calls: int  # tool calls matching expected by name+args
    actual_calls: int  # total tool calls produced
    latency_ms: float | None
    cost_usd: float | None
    # Per-metric provenance (appended with defaults so positional construction is
    # unchanged). latency: "measured" (real span) | "synthetic"; cost: "estimated"
    # (real tokens x static price) | "synthetic". Threaded from CaseTrace.
    latency_source: str = "synthetic"
    cost_source: str = "synthetic"


@dataclass(frozen=True, slots=True)
class ClearDimension:
    name: str
    status: Status
    applicable: bool
    score: float | None  # 0..1 when meaningful, else None
    value: float | None  # raw measurement (ratio / usd / ms)
    unit: str
    basis: str


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def _budget_score(value: float, budget: float | None) -> float | None:
    """Lower-is-better normalization: 1.0 at zero, 0.0 at/above the budget.
    Returns None when no budget/SLO is configured (raw value stands alone)."""
    if budget is None or budget <= 0:
        return None
    return max(0.0, min(1.0, 1.0 - value / budget))


def _accuracy(overall_score: float) -> ClearDimension:
    return ClearDimension(
        "accuracy",
        "measured",
        True,
        overall_score,
        overall_score,
        "ratio",
        "mean of the per-level eval scores (L1/L2/L3)",
    )


def _efficiency(signals: list[CaseSignal]) -> ClearDimension:
    with_calls = [s for s in signals if s.actual_calls > 0]
    if not with_calls:
        return ClearDimension(
            "efficiency", "measured", False, None, None, "ratio", "no tool calls to measure"
        )
    eff = _mean([s.exact_calls / s.actual_calls for s in with_calls])
    return ClearDimension(
        "efficiency",
        "measured",
        True,
        eff,
        eff,
        "ratio",
        "useful (exact) calls / total calls — penalizes redundant, extra, wrong-args calls",
    )


def _reliability(signals: list[CaseSignal]) -> ClearDimension:
    if not signals:
        return ClearDimension(
            "reliability", "measured", False, None, None, "ratio", "no cases to measure"
        )
    rel = _mean(
        [
            1.0 if (s.l1_passed and s.l3_passed and (not s.l2_applicable or s.l2_passed)) else 0.0
            for s in signals
        ]
    )
    return ClearDimension(
        "reliability",
        "measured",
        True,
        rel,
        rel,
        "ratio",
        "end-to-end success rate (all applicable levels pass); cross-run flakiness deferred to F5+",
    )


def _telemetry_dim(
    name: str,
    unit: str,
    pairs: list[tuple[float, str]],
    total: int,
    budget: float | None,
    real_source: str,
    real_status: str,
) -> ClearDimension:
    """Build a Cost/Latency dimension from ``(value, source)`` pairs of traced cases.

    ``real_status`` is the dimension's real-telemetry status ("measured" for latency,
    "estimated" for cost). The dimension reaches that status ONLY when EVERY
    contributing value is from real telemetry; any hand-authored value among them
    honestly downgrades the whole dimension to "synthetic" — one real case cannot
    launder a synthetic suite. The real/traced split is disclosed in the basis either
    way; with no telemetry the dimension is "placeholder".
    """
    if not pairs:
        return ClearDimension(
            name,
            "placeholder",
            False,
            None,
            None,
            unit,
            f"PLACEHOLDER: no telemetry — needs {real_source} (F1.x)",
        )
    value = _mean([v for v, _ in pairs])
    n = len(pairs)
    real = sum(1 for _, source in pairs if source == real_status)
    if real == n:
        kind = (
            "real request span duration"
            if real_status == "measured"
            else "real measured tokens × static list price"
        )
        status = real_status
        basis = f"{real_status.upper()} mean of {n}/{total} traced cases: {kind} (F1.x telemetry)"
    else:
        # Homogeneous rule: any hand-authored value -> synthetic, with the split shown
        # (so a single real datapoint is never mistaken for a real suite average).
        status = "synthetic"
        basis = (
            f"SYNTHETIC mean of {n}/{total} traced cases "
            f"({real} from real telemetry, {n - real} hand-authored); a homogeneous "
            f"real set is needed for '{real_status}' — see {real_source} (F1.x)"
        )
    return ClearDimension(name, status, True, _budget_score(value, budget), value, unit, basis)


def compute_clear(
    signals: list[CaseSignal],
    overall_score: float,
    *,
    latency_budget_ms: float | None = None,
    cost_budget_usd: float | None = None,
) -> dict[str, ClearDimension]:
    """Compute the five CLEAR dimensions for a run, in C-L-E-A-R order."""
    return {
        "cost": _telemetry_dim(
            "cost",
            "usd",
            [(s.cost_usd, s.cost_source) for s in signals if s.cost_usd is not None],
            len(signals),
            cost_budget_usd,
            "provider token usage + price telemetry",
            "estimated",
        ),
        "latency": _telemetry_dim(
            "latency",
            "ms",
            [(s.latency_ms, s.latency_source) for s in signals if s.latency_ms is not None],
            len(signals),
            latency_budget_ms,
            "live request timing via OpenTelemetry",
            "measured",
        ),
        "efficiency": _efficiency(signals),
        "accuracy": _accuracy(overall_score),
        "reliability": _reliability(signals),
    }
