"""Eval-gate baseline: the committed contract the CI gate compares against.

The gate (``aegis eval gate``) runs the eval suite on the DETERMINISTIC, offline
MockJudge/MockProvider and compares the result to a committed baseline
(``src/aegis/evals/baselines/<suite>.json``). It catches regressions in the eval
PIPELINE versus that baseline; it does NOT validate the real judge's behavior —
that is F5 calibration (Cohen's κ), a separate, directional signal.

What the gate guarantees is **no SILENT regression**, not "no regression ever":
a regression becomes a named, blocking, reviewable event, and re-baselining one
is a visible diff in the PR — human review is the final backstop.

``compare_to_baseline`` is a PURE function returning a list of typed
``Regression`` findings (no I/O, no ``sys.exit``), so it is offline-testable with
fixtures and red-team gating (F6) can union its own findings additively later.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
SCORE_DECIMALS = 6
DEFAULT_TOLERANCE = 0.005  # per-level mean-drop band (aggregate backstop)
_LEVELS = ("L1", "L2", "L3")

_TOP_KEYS = frozenset({"suite", "judge", "case_count", "levels", "cases"})
_LEVEL_KEYS = frozenset({"mean_score", "passed", "scored"})
_CASE_KEYS = frozenset(
    {
        "l1_passed",
        "l1_score",
        "l2_applicable",
        "l2_passed",
        "l2_score",
        "l2_parse_failed",
        "l3_passed",
        "l3_score",
    }
)

DEFAULT_BASELINE_DIR = Path(__file__).parent / "baselines"


def baseline_path(suite: str) -> Path:
    """Resolve the committed baseline for a suite (mirrors DEFAULT_GOLDEN_PATH)."""
    return DEFAULT_BASELINE_DIR / f"{suite}.json"


class BaselineError(ValueError):
    """The gate cannot fairly compare (baseline missing / stale / misconfigured).

    Distinct from a genuine regression: the CLI maps this to exit 2 ("regenerate
    the contract"), while a real regression is exit 1 ("your change regressed").
    """


@dataclass(frozen=True, slots=True)
class Regression:
    # kind: level_mean_drop | level_dropped | case_score_drop | case_pass_fail
    #       | l2_dropped | new_parse_failed
    kind: str
    scope: str  # the level name or "<case-id> <level>" — always NAMES what regressed
    detail: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.scope}: {self.detail}"


def _round(x: float) -> float:
    return round(float(x), SCORE_DECIMALS)


def _parse_failed(l2: dict[str, Any]) -> bool:
    """True if the L2 breakdown carries a truthy ``*_parse_failed`` key.

    The key (``relevancy_parse_failed`` / ``faithfulness_parse_failed``) is written
    by l2_trace ONLY when a verdict's ``parse_failed`` is True, which only the real
    GEval/Ensemble judges ever set. Under the forced-mock gate it is therefore
    always absent (False); the parse_failed rule is a LATENT, forward-looking
    tripwire for a future real-judge baseline, never reached by the offline gate.
    """
    breakdown = l2.get("breakdown", {})
    return any(k.endswith("_parse_failed") and v for k, v in breakdown.items())


def to_baseline(report: Any) -> dict[str, Any]:
    """Reduce a Report (or its ``to_dict()``) to the minimal deterministic contract.

    Excludes ``created`` (runtime timestamp), ``clear`` (synthetic), ``trajectory``
    / ``agent_judge`` (F4 process), and free-text reasons — none are part of the
    L1/L2/L3 quality contract. Floats are rounded to SCORE_DECIMALS so the JSON is
    human-diffable and stable across platforms.
    """
    data = report.to_dict() if hasattr(report, "to_dict") else report
    levels = {
        name: {
            "mean_score": _round(lv["mean_score"]),
            "passed": lv["passed"],
            "scored": lv["scored"],
        }
        for name, lv in data["levels"].items()
    }
    cases: dict[str, Any] = {}
    for case in data["cases"]:
        l2 = case["l2"]
        cases[case["id"]] = {
            "l1_passed": bool(case["l1"]["passed"]),
            "l1_score": _round(case["l1"]["score"]),
            "l2_applicable": bool(l2.get("breakdown", {}).get("applicable", False)),
            "l2_passed": bool(l2["passed"]),
            "l2_score": _round(l2["score"]),
            "l2_parse_failed": _parse_failed(l2),
            "l3_passed": bool(case["l3"]["passed"]),
            "l3_score": _round(case["l3"]["score"]),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        "suite": data["suite"],
        "judge": data["judge"],
        "case_count": data["case_count"],
        "score_decimals": SCORE_DECIMALS,
        "levels": levels,
        "overall_score": _round(data["overall_score"]),
        "cases": cases,
    }


def load_baseline(path: str | Path) -> dict[str, Any]:
    """Load + lightly validate a committed baseline; raise BaselineError (exit 2)
    on a missing file, bad JSON, or a schema-version mismatch."""
    p = Path(path)
    if not p.exists():
        raise BaselineError(f"baseline not found: {p} (run: aegis eval gate --update-baseline)")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BaselineError(f"baseline is not valid JSON: {p}: {exc.msg}") from exc
    if data.get("schema_version") != SCHEMA_VERSION:
        raise BaselineError(
            f"baseline schema_version {data.get('schema_version')!r} != {SCHEMA_VERSION} "
            f"— regenerate with: aegis eval gate --update-baseline"
        )
    missing = _TOP_KEYS - data.keys()
    if missing:
        raise BaselineError(
            f"baseline malformed: missing top-level keys {sorted(missing)} "
            f"— regenerate with: aegis eval gate --update-baseline"
        )
    return data


def _level_regressions(baseline: dict, current: dict, tolerance: float) -> list[Regression]:
    out: list[Regression] = []
    for lv in _LEVELS:
        b = baseline["levels"].get(lv)
        if b is None:
            continue
        c = current["levels"].get(lv)
        if c is None:
            out.append(
                Regression("level_dropped", lv, f"level disappeared (was scored={b['scored']})")
            )
            continue
        if c["mean_score"] < b["mean_score"] - tolerance:
            out.append(
                Regression(
                    "level_mean_drop",
                    lv,
                    f"mean {c['mean_score']:.6f} < {b['mean_score']:.6f} (baseline) "
                    f"by {b['mean_score'] - c['mean_score']:.6f} > tol {tolerance}",
                )
            )
    return out


def _case_regressions(baseline: dict, current: dict) -> list[Regression]:
    out: list[Regression] = []
    for cid in sorted(baseline["cases"]):
        b = baseline["cases"][cid]
        c = current["cases"][cid]
        # L1 / L3 always apply: a per-case score drop (exact after rounding) OR a
        # pass->fail flip is a regression. (Passing L1/L3 cases score exactly 1.0,
        # so a flip always co-fires, but the score check is the general guard.)
        for lv, score_key, pass_key in (
            ("L1", "l1_score", "l1_passed"),
            ("L3", "l3_score", "l3_passed"),
        ):
            if _round(c[score_key]) < _round(b[score_key]):
                out.append(
                    Regression(
                        "case_score_drop",
                        f"{cid} {lv}",
                        f"score {c[score_key]:.6f} < {b[score_key]:.6f} (baseline)",
                    )
                )
            if b[pass_key] and not c[pass_key]:
                out.append(Regression("case_pass_fail", f"{cid} {lv}", "pass -> fail"))
        # L2 only when the case was applicable in the baseline.
        if b["l2_applicable"]:
            if not c["l2_applicable"]:
                out.append(
                    Regression(
                        "l2_dropped", cid, "L2 applicable true -> false (left the judged set)"
                    )
                )
            else:
                if _round(c["l2_score"]) < _round(b["l2_score"]):
                    out.append(
                        Regression(
                            "case_score_drop",
                            f"{cid} L2",
                            f"score {c['l2_score']:.6f} < {b['l2_score']:.6f} (baseline)",
                        )
                    )
                if b["l2_passed"] and not c["l2_passed"]:
                    out.append(Regression("case_pass_fail", f"{cid} L2", "pass -> fail"))
        # NEW parse failure — HARD, regardless of score (latent under the mock).
        if c["l2_parse_failed"] and not b["l2_parse_failed"]:
            out.append(
                Regression(
                    "new_parse_failed",
                    f"{cid} L2",
                    "NEW parse failure — judge did not actually measure",
                )
            )
    return out


def compare_to_baseline(
    baseline: dict[str, Any], current: dict[str, Any], *, tolerance: float = DEFAULT_TOLERANCE
) -> list[Regression]:
    """Compare a fresh baseline-shaped dict against the committed one.

    Returns a list of typed regressions (empty == pass). Improvements (higher
    scores, fail->pass) never produce a regression. Raises BaselineError (exit 2)
    when the gate cannot fairly compare: judge mismatch or an id-set change (a
    golden case added/removed — the contract is stale and must be regenerated).
    """
    if current["judge"] != baseline["judge"]:
        raise BaselineError(
            f"judge {current['judge']!r} != baseline {baseline['judge']!r} "
            f"— the gate only compares the deterministic mock"
        )
    b_ids = set(baseline["cases"])
    c_ids = set(current["cases"])
    if b_ids != c_ids:
        added = sorted(c_ids - b_ids)
        removed = sorted(b_ids - c_ids)
        raise BaselineError(
            "baseline stale: golden case-set changed "
            f"(added={added}, removed={removed}); run: aegis eval gate --update-baseline"
        )
    _require_well_formed(baseline)
    return _level_regressions(baseline, current, tolerance) + _case_regressions(baseline, current)


def _require_well_formed(baseline: dict[str, Any]) -> None:
    """Raise BaselineError (-> exit 2) if a hand-edited baseline dropped a per-level
    or per-case key, so a malformed contract is a clean 'regenerate' message rather
    than a raw KeyError + traceback deep in the comparator."""
    for lv, level in baseline["levels"].items():
        missing = _LEVEL_KEYS - level.keys()
        if missing:
            raise BaselineError(
                f"baseline malformed: level {lv!r} missing keys {sorted(missing)} "
                f"— regenerate with: aegis eval gate --update-baseline"
            )
    for cid, case in baseline["cases"].items():
        missing = _CASE_KEYS - case.keys()
        if missing:
            raise BaselineError(
                f"baseline malformed: case {cid!r} missing keys {sorted(missing)} "
                f"— regenerate with: aegis eval gate --update-baseline"
            )
