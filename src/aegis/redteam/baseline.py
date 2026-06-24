"""Red-team-gate baseline: the committed contract the CI gate compares against (F7).

The gate (``aegis redteam gate``) scores the committed attack catalog against the F2
guardrails under the HERMETIC, offline ``build_redteam_settings`` (the same scoring
path as the F6 report, via ``redteam.runner.scan``) and compares the result to a
committed baseline (``src/aegis/redteam/baselines/<suite>.json``). It catches
regressions in guardrail DETECTION versus that baseline; it does NOT measure total
security (the detection rate is coverage-against-catalog and INCLUDES the named gaps).

Anti-downgrade core: the baseline records each attack's PRIOR OBSERVED outcome
(blocked/redacted/passed) under the deterministic pipeline, INDEPENDENT of the
catalog's authored ``expected_outcome``/``is_known_gap``. A regression is keyed off
that frozen observed state, NEVER the catalog's current labels — so weakening a
guardrail and relabeling the now-passing attack a "known gap" in the same PR STILL
fails (``attack_now_passing``), because a catalog edit cannot override the baseline.

What the gate guarantees is **no SILENT regression**, not "no regression ever": the
only green path past a real weakening is ``--update-baseline``, which writes a visible
blocked/redacted -> passed diff into the committed file that a human must approve.

``compare_redteam_to_baseline`` is a PURE function returning a list of typed
``RedteamFinding``s (reused from ``redteam.findings``; the structural twin of
``evals.baseline.Regression``), so it is offline-testable and a future ``aegis gate``
umbrella can union it with ``compare_to_baseline`` additively.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from aegis.redteam.findings import RedteamFinding
from aegis.redteam.outcome import AttackResult
from aegis.redteam.report import RedTeamReport

REDTEAM_SCHEMA_VERSION = 1
RATE_DECIMALS = 6
REDTEAM_DEFAULT_TOLERANCE = 0.0  # per-category detection-rate drop band
# Discriminant pinning the comparison to the hermetic offline pipeline. Today the
# only producer is build_redteam_settings, so this is a LATENT tripwire (like the
# eval gate's judge=='mock'): a future real-pipeline mode would mismatch -> exit 2.
REDTEAM_MODE = "mock-offline"

_CAUGHT = ("blocked", "redacted")
_OUTCOMES = ("blocked", "redacted", "passed")

# Findings that BLOCK the merge (exit 1). block_code_changed is INFORMATIONAL (exit
# 0): the guardrail codes have no strength ordering and the short-circuit pipeline can
# legitimately change which stage fires, so a code change while still blocked is
# surfaced as a note, never a failure.
REGRESSION_KINDS = frozenset(
    {"attack_now_passing", "detection_downgraded", "category_detection_drop", "category_dropped"}
)
# The per-attack finding that actually CONSUMES a category's detection-rate loss
# (caught -> passed). Used to de-duplicate the per-category aggregate so one root cause
# is not printed twice. detection_downgraded (block -> redact) keeps the attack caught,
# so it does NOT lower the rate and must NOT suppress an independent category drop.
_RATE_CONSUMING_KINDS = frozenset({"attack_now_passing"})

_TOP_KEYS = frozenset({"suite", "mode", "case_count", "categories", "attacks"})
_CAT_KEYS = frozenset({"total", "blocked", "redacted", "passed", "caught", "detection_rate"})
_ATTACK_KEYS = frozenset({"category", "outcome", "code"})

DEFAULT_BASELINE_DIR = Path(__file__).parent / "baselines"


def redteam_baseline_path(suite: str) -> Path:
    """Resolve the committed red-team baseline for a suite (mirrors baseline_path)."""
    return DEFAULT_BASELINE_DIR / f"{suite}.json"


class RedteamBaselineError(ValueError):
    """The gate cannot fairly compare (baseline missing / stale / misconfigured).

    Distinct from a genuine regression: the CLI maps this to exit 2 ("regenerate the
    contract"), while a real regression is exit 1 ("your change regressed").
    """


def to_redteam_baseline(report: RedTeamReport, results: Sequence[AttackResult]) -> dict[str, Any]:
    """Reduce a run to the minimal deterministic contract.

    ``results`` is load-bearing: the per-attack OBSERVED outcome+code lives only there
    (RedTeamReport aggregates it away). Per-category counts come from the report, so
    ``detection_rate`` reuses report._rate's 6-dp rounding (never a re-implemented
    round). Catalog-authored fields (expected_outcome, is_known_gap, gap_reason,
    payload, role, vector, owasp, tags, description), runtime noise (created), and the
    derivable overall_detection_rate are EXCLUDED — precisely the fields the gate must
    NOT trust. ``caught`` (detected) is NOT stored per attack; it is derived in the
    comparator from ``outcome``, so a hand-edit cannot make a redundant flag lie.
    """
    categories = {
        cat: {
            "total": st.total,
            "blocked": st.blocked,
            "redacted": st.redacted,
            "passed": st.passed,
            "caught": st.blocked + st.redacted,
            "detection_rate": st.detection_rate,  # already round-6 from build_report
        }
        for cat, st in sorted(report.categories.items())
    }
    attacks = {
        r.case.id: {"category": r.case.category, "outcome": r.outcome, "code": r.code}
        for r in results
    }
    return {
        "schema_version": REDTEAM_SCHEMA_VERSION,
        "suite": report.suite,
        "mode": REDTEAM_MODE,
        "rate_decimals": RATE_DECIMALS,
        "case_count": report.case_count,
        "categories": categories,
        "attacks": attacks,
    }


def load_redteam_baseline(path: str | Path) -> dict[str, Any]:
    """Load + lightly validate a committed baseline; raise RedteamBaselineError (exit
    2) on a missing file, bad JSON, a schema-version mismatch, or a missing top key."""
    p = Path(path)
    if not p.exists():
        raise RedteamBaselineError(
            f"red-team baseline not found: {p} (run: aegis redteam gate --update-baseline)"
        )
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RedteamBaselineError(f"red-team baseline is not valid JSON: {p}: {exc.msg}") from exc
    if data.get("schema_version") != REDTEAM_SCHEMA_VERSION:
        raise RedteamBaselineError(
            f"red-team baseline schema_version {data.get('schema_version')!r} != "
            f"{REDTEAM_SCHEMA_VERSION} — regenerate with: aegis redteam gate --update-baseline"
        )
    missing = _TOP_KEYS - data.keys()
    if missing:
        raise RedteamBaselineError(
            f"red-team baseline malformed: missing top-level keys {sorted(missing)} "
            f"— regenerate with: aegis redteam gate --update-baseline"
        )
    return data


def _rate(num: int, den: int) -> float:
    """Detection rate rounded like report._rate (den==0 -> 0.0), so the well-formed
    check re-derives the stored rate with the exact same idiom that produced it."""
    return round(num / den, RATE_DECIMALS) if den else 0.0


def _require_well_formed(data: dict[str, Any], *, check_rate: bool = True) -> None:
    """Raise RedteamBaselineError (-> exit 2) for a hand-corrupted/inconsistent contract,
    so a dropped/lying key is a clean 'regenerate' message rather than a raw KeyError (or
    a trusted lie) deep in the comparator. Validates both the committed `baseline` and the
    machine-built `current` (a no-op on the latter, by construction). Closes the honesty
    seams: per-category counts must be internally consistent; the category set must match
    the categories present in the attacks; and a per-attack code is non-null IFF the
    outcome is 'blocked' (classify_result guarantees redacted/passed carry code=None).

    ``check_rate`` re-derives the stored ``detection_rate`` from caught/total. It is ON for
    the BASELINE — the hand-editable floor ``_category_regressions`` trusts, so a fabricated
    rate cannot lie there — and OFF for the CURRENT, whose ``detection_rate`` is the live
    measurement the aggregate rule evaluates against that (validated) baseline floor."""
    for cat, stat in data["categories"].items():
        missing = _CAT_KEYS - stat.keys()
        if missing:
            raise RedteamBaselineError(
                f"red-team baseline malformed: category {cat!r} missing keys {sorted(missing)} "
                f"— regenerate with: aegis redteam gate --update-baseline"
            )
        if stat["caught"] != stat["blocked"] + stat["redacted"]:
            raise RedteamBaselineError(
                f"red-team baseline malformed: category {cat!r} caught != blocked+redacted"
            )
        if stat["total"] != stat["blocked"] + stat["redacted"] + stat["passed"]:
            raise RedteamBaselineError(
                f"red-team baseline malformed: category {cat!r} total != blocked+redacted+passed"
            )
        # The baseline rate is stored AND trusted as the floor by _category_regressions, so
        # re-derive it (like `caught` is derived per attack) — a fabricated floor can't lie.
        if check_rate and stat["detection_rate"] != _rate(stat["caught"], stat["total"]):
            raise RedteamBaselineError(
                f"red-team baseline malformed: category {cat!r} detection_rate != caught/total"
            )
    # The category set must equal the categories actually present in the attacks, else a
    # phantom category could reach the (otherwise unreachable) category_dropped branch.
    attack_cats = {atk.get("category") for atk in data["attacks"].values()}
    if set(data["categories"]) != attack_cats:
        raise RedteamBaselineError(
            "red-team baseline malformed: category set != categories present in attacks "
            "— regenerate with: aegis redteam gate --update-baseline"
        )
    for aid, atk in data["attacks"].items():
        missing = _ATTACK_KEYS - atk.keys()
        if missing:
            raise RedteamBaselineError(
                f"red-team baseline malformed: attack {aid!r} missing keys {sorted(missing)} "
                f"— regenerate with: aegis redteam gate --update-baseline"
            )
        if atk["outcome"] not in _OUTCOMES:
            raise RedteamBaselineError(
                f"red-team baseline malformed: attack {aid!r} invalid outcome {atk['outcome']!r}"
            )
        if (atk["code"] is not None) != (atk["outcome"] == "blocked"):
            raise RedteamBaselineError(
                f"red-team baseline malformed: attack {aid!r} code set iff outcome=='blocked'"
            )


def _attack_regressions(baseline: dict, current: dict) -> list[RedteamFinding]:
    out: list[RedteamFinding] = []
    for aid in sorted(baseline["attacks"]):
        b = baseline["attacks"][aid]
        c = current["attacks"][aid]
        # A bucket remap is a contract change, not a regression -> exit 2 (re-baseline);
        # otherwise a category swap could mask the per-category aggregate backstop.
        if b["category"] != c["category"]:
            raise RedteamBaselineError(
                f"red-team baseline stale: attack {aid!r} category "
                f"{b['category']!r} -> {c['category']!r}; run: aegis redteam gate --update-baseline"
            )
        scope = f"{aid} {b['category']}"
        b_caught = b["outcome"] in _CAUGHT
        if b_caught and c["outcome"] == "passed":
            # THE anti-downgrade lock: reads ONLY the baseline's frozen caught state and
            # the current observed outcome; never the catalog's expected_outcome /
            # is_known_gap, so relabeling the now-passing attack a gap cannot suppress it.
            out.append(
                RedteamFinding(
                    "attack_now_passing",
                    scope,
                    f"was {b['outcome']} in the baseline, now passes undetected",
                )
            )
        elif b["outcome"] == "blocked" and c["outcome"] == "redacted":
            # The monotone-weakening half a block -> a mere redaction stays "caught", so
            # attack_now_passing misses it. redacted -> blocked is an improvement (no fire).
            out.append(
                RedteamFinding(
                    "detection_downgraded",
                    scope,
                    "was blocked in the baseline, now only redacted",
                )
            )
        elif b["outcome"] == "blocked" and c["outcome"] == "blocked" and b["code"] != c["code"]:
            # INFORMATIONAL (not in REGRESSION_KINDS): codes have no strength ordering and
            # the short-circuit pipeline can legitimately change which stage fires.
            out.append(
                RedteamFinding(
                    "block_code_changed",
                    scope,
                    f"still blocked but code {b['code']} -> {c['code']} (informational)",
                )
            )
    return out


def _category_regressions(
    baseline: dict, current: dict, tolerance: float, attack_findings: list[RedteamFinding]
) -> list[RedteamFinding]:
    # Categories whose rate drop is already explained by a per-attack attack_now_passing
    # (the only per-attack finding that lowers detection_rate): don't print the same root
    # cause twice. scope of a per-attack finding is "<id> <category>".
    explained = {f.scope.split()[-1] for f in attack_findings if f.kind in _RATE_CONSUMING_KINDS}
    out: list[RedteamFinding] = []
    for cat in sorted(baseline["categories"]):
        b = baseline["categories"][cat]
        c = current["categories"].get(cat)
        if c is None:
            # A whole bucket vanished on the matched id-set. Unreachable after the id-set
            # guard (which exits 2 first); kept as a typed safety net, not advertised as a
            # deletion defense (deleting a category's attacks is an id-set change -> exit 2).
            out.append(
                RedteamFinding(
                    "category_dropped", cat, f"category disappeared (was total={b['total']})"
                )
            )
            continue
        if c["detection_rate"] < b["detection_rate"] - tolerance and cat not in explained:
            out.append(
                RedteamFinding(
                    "category_detection_drop",
                    cat,
                    f"detection {c['detection_rate']:.6f} < {b['detection_rate']:.6f} (baseline) "
                    f"by {b['detection_rate'] - c['detection_rate']:.6f} > tol {tolerance}",
                )
            )
    return out


def compare_redteam_to_baseline(
    baseline: dict[str, Any],
    current: dict[str, Any],
    *,
    tolerance: float = REDTEAM_DEFAULT_TOLERANCE,
) -> list[RedteamFinding]:
    """Compare a fresh baseline-shaped dict against the committed one.

    Returns a list of typed findings (empty == pass; only REGRESSION_KINDS block).
    Improvements (a gap newly caught, redacted->blocked, a higher detection rate) never
    produce a finding. Raises RedteamBaselineError (exit 2) when the gate cannot fairly
    compare: suite/mode mismatch, an attack id-set change, a category remap, or a
    malformed baseline OR current. Both sides are read defensively (``.get`` + a
    well-formed check), so a hand-built/future ``current`` yields the clean exit-2 path
    rather than a raw KeyError the CLI would not catch.
    """
    if current.get("suite") != baseline["suite"]:
        raise RedteamBaselineError(
            f"suite {current.get('suite')!r} != baseline {baseline['suite']!r}"
        )
    if current.get("mode") != baseline.get("mode"):
        raise RedteamBaselineError(
            f"mode {current.get('mode')!r} != baseline {baseline.get('mode')!r} "
            f"— the gate only compares the hermetic offline pipeline"
        )
    b_ids = set(baseline["attacks"])
    c_ids = set(current["attacks"])
    if b_ids != c_ids:
        added = sorted(c_ids - b_ids)
        removed = sorted(b_ids - c_ids)
        raise RedteamBaselineError(
            "red-team baseline stale: attack-set changed "
            f"(added={added}, removed={removed}); run: aegis redteam gate --update-baseline"
        )
    _require_well_formed(baseline)
    # Validate current's structure too (guards the pure API against a raw KeyError), but
    # NOT its rate — that's the live measurement the aggregate rule reads vs the baseline.
    _require_well_formed(current, check_rate=False)
    attack_findings = _attack_regressions(baseline, current)
    return attack_findings + _category_regressions(baseline, current, tolerance, attack_findings)
