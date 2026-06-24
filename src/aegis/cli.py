"""Aegis command-line interface (stdlib argparse, no extra deps).

Subcommands:
  ``aegis eval run`` — run the eval suite over a golden set (L1/L2/L3 + F4
  trajectory metrics, the Agent-as-a-Judge, and the CLEAR dimensions) and write a
  JSON report.
  ``aegis calibrate`` — score the configured judge over the hand-labeled
  calibration set and write a Cohen's-kappa agreement report (per criterion +
  global). The real run needs ANTHROPIC_API_KEY + the ``[anthropic]`` extra; with
  no key it exits 2 cleanly. The kappa is DIRECTIONAL (see the README caveats).
  ``aegis eval gate`` — the real F7 CI gate: run the suite on the DETERMINISTIC,
  offline mock and compare to the committed baseline; exit non-zero on regression
  (1) or a stale/misconfigured baseline (2). ``--update-baseline`` regenerates the
  committed contract. It gates EVAL regressions only (red-team gating lands later)
  and does NOT validate the real judge (that is F5 kappa).
  ``aegis redteam run`` — run a committed catalog of synthetic attacks DIRECTLY
  against the F2 guardrails (offline, keyless) and report a per-OWASP-category
  detection rate (F6). Coverage-against-catalog, NOT total security; passing
  attacks are surfaced as named gaps. It REPORTS, it does not gate.

``aegis eval run`` keeps a separate ``--fail-under`` seam: a manual ABSOLUTE floor
on the overall score (exit 1 only when explicitly passed), complementary to the
baseline-comparing gate above — kept, not replaced.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from aegis.evals.baseline import (
    DEFAULT_TOLERANCE,
    BaselineError,
    baseline_path,
    compare_to_baseline,
    load_baseline,
    to_baseline,
)
from aegis.evals.calibration.dataset import (
    DEFAULT_CALIBRATION_PATH,
    CalibrationDatasetError,
    load_calibration,
)
from aegis.evals.calibration.runner import run_calibration
from aegis.evals.dataset import DEFAULT_GOLDEN_PATH, GoldenDatasetError, load_golden
from aegis.evals.judge.agent import MockTrajectoryJudge, build_trajectory_judge
from aegis.evals.judge.factory import build_judge
from aegis.evals.judge.geval import JudgeNotConfiguredError
from aegis.evals.judge.mock import MockJudge
from aegis.evals.persistence import (
    DEFAULT_REPORTS_DIR,
    write_baseline,
    write_calibration_report,
    write_redteam_report,
    write_report,
)
from aegis.evals.runner import run_suite
from aegis.evidence.builder import build_evidence
from aegis.evidence.loader import EvidenceInputError, read_report
from aegis.evidence.persistence import write_evidence_json
from aegis.gateway.config import get_settings
from aegis.gateway.errors import ProviderNotConfiguredError
from aegis.redteam.dataset import DEFAULT_ATTACKS_PATH, AttackDatasetError, load_attacks
from aegis.redteam.runner import run_redteam

_CLEAR_ORDER = ("cost", "latency", "efficiency", "accuracy", "reliability")


def _format_clear(dim: dict) -> str:
    """Compact one-token rendering of a CLEAR dimension.

    'measured' is the trusted baseline and renders clean; 'estimated', 'synthetic',
    and 'placeholder' carry their status suffix so non-measured data is never mistaken
    for a real measurement (applies on both the scored and raw-value paths)."""
    if not dim["applicable"]:
        return f"{dim['name']}=n/a({dim['status']})"
    suffix = "" if dim["status"] == "measured" else f"({dim['status']})"
    if dim["score"] is not None:
        return f"{dim['name']}={dim['score']:.3f}{suffix}"
    return f"{dim['name']}={dim['value']:.3g}{dim['unit']}{suffix}"


def _eval_run(args: argparse.Namespace) -> int:
    settings = get_settings()
    if args.judge:
        settings = settings.model_copy(update={"judge_backend": args.judge})

    try:
        cases = load_golden(args.dataset)
        judge = build_judge(settings)
        traj_judge = build_trajectory_judge(settings)
        report = run_suite(
            cases,
            judge,
            traj_judge,
            suite=args.suite,
            created=int(time.time()),
            latency_budget_ms=settings.clear_latency_budget_ms,
            cost_budget_usd=settings.clear_cost_budget_usd,
        )
    except (GoldenDatasetError, JudgeNotConfiguredError, ProviderNotConfiguredError) as exc:
        # A real judge selected with no key/SDK -> clean exit 2, never an offline crash.
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out = args.output or (DEFAULT_REPORTS_DIR / f"eval-{args.suite}.json")
    write_report(report, out)

    print(f"suite={report.suite} judge={report.judge} cases={report.case_count}")
    for level in ("L1", "L2", "L3"):
        agg = report.levels.get(level)
        if agg:
            print(f"  {level}: mean={agg.mean_score:.3f} passed={agg.passed}/{agg.scored}")
    if report.trajectory:
        traj = "  ".join(f"{k}={v['mean_score']:.3f}" for k, v in report.trajectory.items())
        print(f"  trajectory: {traj}")
    if report.clear:
        print(f"  CLEAR: {'  '.join(_format_clear(report.clear[k]) for k in _CLEAR_ORDER)}")
    print(f"overall={report.overall_score:.3f}  report={out}")

    if args.fail_under is not None and report.overall_score < args.fail_under:
        print(
            f"FAIL: overall {report.overall_score:.3f} < fail-under {args.fail_under}",
            file=sys.stderr,
        )
        return 1
    return 0


def _fmt_stat(x: float | None) -> str:
    return "undefined" if x is None else f"{x:.3f}"


def _calibrate_scope_line(name: str, section) -> str:
    r = section.result
    return (
        f"  {name}: kappa={_fmt_stat(r.kappa)} p_o={_fmt_stat(r.p_o)} "
        f"n_valid={r.n_valid} parse_failed={section.n_parse_failed} band={r.band}"
    )


def _calibrate(args: argparse.Namespace) -> int:
    settings = get_settings()
    if args.judge:
        settings = settings.model_copy(update={"judge_backend": args.judge})

    try:
        cases = load_calibration(args.dataset)
        judge = build_judge(settings)
        report = run_calibration(cases, judge, created=int(time.time()))
    except (CalibrationDatasetError, JudgeNotConfiguredError, ProviderNotConfiguredError) as exc:
        # A real judge selected with no key/SDK -> clean exit 2, never an offline crash.
        print(f"error: {exc}", file=sys.stderr)
        return 2

    out = args.output or (DEFAULT_REPORTS_DIR / "calibration.json")
    write_calibration_report(report, out)

    if report.judge == "mock":
        # The mock is lexical, not the judge being calibrated — its kappa measures
        # the mock against the labels, not a real calibration.
        print(
            "note: the mock judge is a wiring smoke test, not a real calibration; "
            "use --judge geval with ANTHROPIC_API_KEY for the real measurement",
            file=sys.stderr,
        )

    dataset = args.dataset or DEFAULT_CALIBRATION_PATH
    print(f"dataset={dataset} judge={report.judge} cases={report.n_cases}")
    print(_calibrate_scope_line("relevancy", report.per_criterion["relevancy"]))
    print(_calibrate_scope_line("faithfulness", report.per_criterion["faithfulness"]))
    print(_calibrate_scope_line("global", report.global_))
    print("(Landis-Koch bands are arbitrary conventions; read kappa with p_o + the matrix)")
    print(f"report={out}")
    return 0


def _eval_gate(args: argparse.Namespace) -> int:
    # The gate is deterministic + offline BY CONSTRUCTION: build BOTH judges as the
    # keyless mocks directly (never via settings/factory), so no AEGIS_JUDGE_BACKEND
    # / AEGIS_AGENT_JUDGE_BACKEND env var can route it to a real, networked judge.
    try:
        cases = load_golden(args.dataset)
    except GoldenDatasetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    report = run_suite(cases, MockJudge(), MockTrajectoryJudge(), suite=args.suite, created=0)
    current = to_baseline(report)
    out = args.baseline or baseline_path(args.suite)

    if args.update_baseline:
        write_baseline(current, out)
        print(
            f"wrote baseline {out} "
            f"(suite={current['suite']} judge={current['judge']} cases={current['case_count']})"
        )
        return 0

    try:
        baseline = load_baseline(out)
        regressions = compare_to_baseline(baseline, current, tolerance=args.tolerance)
    except BaselineError as exc:
        # Cannot fairly compare (missing/stale/misconfigured) -> exit 2, not 1.
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if regressions:
        print(f"FAIL: {len(regressions)} eval regression(s) vs baseline {out}:", file=sys.stderr)
        for reg in regressions:
            print(f"  {reg}", file=sys.stderr)
        return 1

    print(
        f"PASS: no eval regressions vs baseline {out} ({current['case_count']} cases, judge=mock)"
    )
    return 0


def _redteam_run(args: argparse.Namespace) -> int:
    try:
        cases = load_attacks(args.dataset)
    except AttackDatasetError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = run_redteam(cases, suite=args.suite, created=int(time.time()))
    out = args.output or (DEFAULT_REPORTS_DIR / f"redteam-{args.suite}.json")
    write_redteam_report(report, out)

    detected = sum(st.blocked + st.redacted for st in report.categories.values())
    print(f"suite={report.suite} cases={report.case_count}")
    for cat in sorted(report.categories):
        st = report.categories[cat]
        owasp = st.owasp or "no clean OWASP slot"
        print(
            f"  {cat} ({owasp}): detected={st.blocked + st.redacted}/{st.total} "
            f"rate={st.detection_rate:.3f} passed={st.passed}"
        )
    rate = report.overall_detection_rate
    print(f"  overall: detected={detected}/{report.case_count} rate={rate:.3f}")

    # Passing attacks are SURFACED, never hidden — coverage-against-catalog, not total security.
    if report.known_gaps:
        print(f"  known gaps (passed by design): {len(report.known_gaps)}")
        for gap in report.known_gaps:
            print(f"    {gap['id']} [{gap['category']}]: {gap['gap_reason']}")
    if report.findings:
        print(f"  UNEXPECTED findings: {len(report.findings)}", file=sys.stderr)
        for finding in report.findings:
            print(f"    {finding}", file=sys.stderr)
    print(f"report={out}")

    # Opt-in absolute floor (mirrors eval run --fail-under); NOT the red-team gate.
    if (
        args.fail_under_detection is not None
        and report.overall_detection_rate < args.fail_under_detection
    ):
        print(
            f"FAIL: detection {report.overall_detection_rate:.3f} < "
            f"fail-under-detection {args.fail_under_detection}",
            file=sys.stderr,
        )
        return 1
    return 0


def _evidence(args: argparse.Namespace) -> int:
    # Per-source resolution (the three reports use DIFFERENT default suites): the eval
    # report follows --suite (default golden), the red-team report its own default
    # filename (redteam-redteam.json), calibration is path-only. A path the user passes
    # explicitly is `required` (a typo must not silently vanish into not_covered).
    suite = args.suite
    eval_path = Path(args.eval) if args.eval else DEFAULT_REPORTS_DIR / f"eval-{suite}.json"
    redteam_path = (
        Path(args.redteam) if args.redteam else DEFAULT_REPORTS_DIR / "redteam-redteam.json"
    )
    calib_path = (
        Path(args.calibration) if args.calibration else DEFAULT_REPORTS_DIR / "calibration.json"
    )
    try:
        eval_report = read_report(eval_path, required=args.eval is not None)
        redteam_report = read_report(redteam_path, required=args.redteam is not None)
        calibration_report = read_report(calib_path, required=args.calibration is not None)
    except EvidenceInputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = build_evidence(
        eval_report=eval_report,
        redteam_report=redteam_report,
        calibration_report=calibration_report,
        settings=get_settings(),
        suite=suite,
        generated=int(time.time()),
    )

    if args.format == "json":
        out = Path(args.output) if args.output else DEFAULT_REPORTS_DIR / f"evidence-{suite}.json"
        write_evidence_json(report, out)
    else:
        # Lazy-import the renderer ONLY on the pdf path, so --format json never needs
        # fpdf2 (even transitively). A missing [reporting] extra is a clean exit 2.
        from aegis.evidence.pdf import EvidenceRenderError, render_pdf

        out = Path(args.output) if args.output else DEFAULT_REPORTS_DIR / f"evidence-{suite}.pdf"
        try:
            render_pdf(report, out)
        except EvidenceRenderError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    if args.json:
        write_evidence_json(report, args.json)

    sc = report.summary_counts
    print(
        f"evidence: controls={len(report.controls)} covered={sc['covered']} "
        f"partial={sc['partial']} not_covered={sc['not_covered']} "
        f"out_of_scope={sc['out_of_scope']}  report={out}"
    )
    # Surface every not-covered control (with its produce-it hint) — never hidden.
    for c in report.controls:
        if c.status == "not_covered":
            print(
                f"  not covered: {c.framework} {c.control_id} - {c.derived_value}", file=sys.stderr
            )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="aegis", description="Aegis gateway tooling.")
    groups = parser.add_subparsers(dest="group", required=True)

    eval_group = groups.add_parser("eval", help="evaluation commands")
    eval_cmds = eval_group.add_subparsers(dest="command", required=True)

    run_cmd = eval_cmds.add_parser("run", help="run the eval suite over a golden set")
    run_cmd.add_argument(
        "--dataset", default=None, help=f"golden JSONL path (default: {DEFAULT_GOLDEN_PATH})"
    )
    run_cmd.add_argument("--suite", default="golden", help="suite name recorded in the report")
    run_cmd.add_argument(
        "--judge",
        choices=["mock", "geval", "ensemble"],
        default=None,
        help="override judge backend",
    )
    run_cmd.add_argument("--output", default=None, help="report JSON path")
    run_cmd.add_argument(
        "--fail-under",
        type=float,
        default=None,
        help="exit non-zero if overall < threshold (CI gate seam; off unless passed)",
    )
    run_cmd.set_defaults(func=_eval_run)

    # `aegis eval gate` — the F7 regression gate: deterministic offline mock vs the
    # committed baseline; exit 1 on regression, 2 on a stale/misconfigured baseline.
    gate_cmd = eval_cmds.add_parser(
        "gate", help="block on eval regression vs the committed baseline (offline, mock)"
    )
    gate_cmd.add_argument(
        "--dataset", default=None, help=f"golden JSONL path (default: {DEFAULT_GOLDEN_PATH})"
    )
    gate_cmd.add_argument(
        "--suite", default="golden", help="suite name (selects the baseline file)"
    )
    gate_cmd.add_argument(
        "--baseline",
        default=None,
        help="baseline JSON path (default: src/aegis/evals/baselines/<suite>.json)",
    )
    gate_cmd.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE,
        help=f"per-level mean-drop tolerance (default: {DEFAULT_TOLERANCE})",
    )
    gate_cmd.add_argument(
        "--update-baseline",
        action="store_true",
        help="regenerate + write the baseline from a fresh mock run, then exit 0 (no compare)",
    )
    gate_cmd.set_defaults(func=_eval_gate)

    # `aegis calibrate` is a single-action group (no sub-command): measure
    # judge-vs-human agreement (Cohen's kappa) over the calibration set.
    cal_cmd = groups.add_parser("calibrate", help="measure judge-human agreement (Cohen's kappa)")
    cal_cmd.add_argument(
        "--dataset",
        default=None,
        help=f"calibration JSONL path (default: {DEFAULT_CALIBRATION_PATH})",
    )
    cal_cmd.add_argument(
        "--judge",
        choices=["mock", "geval", "ensemble"],
        default=None,
        help="override judge backend (default: settings; geval is the real calibration)",
    )
    cal_cmd.add_argument("--output", default=None, help="report JSON path")
    cal_cmd.set_defaults(func=_calibrate)

    # `aegis redteam run` — offline synthetic attacks vs the F2 guardrails (F6).
    rt_group = groups.add_parser("redteam", help="red-team the guardrails (OWASP, offline)")
    rt_cmds = rt_group.add_subparsers(dest="command", required=True)
    rt_run = rt_cmds.add_parser("run", help="run the attack catalog; report per-category detection")
    rt_run.add_argument(
        "--dataset", default=None, help=f"attack JSONL path (default: {DEFAULT_ATTACKS_PATH})"
    )
    rt_run.add_argument("--suite", default="redteam", help="suite name recorded in the report")
    rt_run.add_argument("--output", default=None, help="report JSON path")
    rt_run.add_argument(
        "--fail-under-detection",
        type=float,
        default=None,
        help="exit 1 if overall detection rate < floor (opt-in; NOT the red-team gate)",
    )
    rt_run.set_defaults(func=_redteam_run)

    # `aegis evidence` — single-action group (F8): build a PARTIAL-TECHNICAL-EVIDENCE
    # PDF (or JSON) from the real eval/red-team/calibration reports + effective config.
    ev_cmd = groups.add_parser(
        "evidence", help="generate a partial governance-evidence doc from real reports"
    )
    ev_cmd.add_argument(
        "--suite", default="golden", help="eval suite name (eval report filename + output naming)"
    )
    ev_cmd.add_argument(
        "--eval", default=None, help="eval report path (default: reports/eval-<suite>.json)"
    )
    ev_cmd.add_argument(
        "--redteam",
        default=None,
        help="red-team report path (default: reports/redteam-redteam.json)",
    )
    ev_cmd.add_argument(
        "--calibration",
        default=None,
        help="calibration report path (default: reports/calibration.json)",
    )
    ev_cmd.add_argument(
        "--output", default=None, help="output path (default: reports/evidence-<suite>.<ext>)"
    )
    ev_cmd.add_argument(
        "--json", default=None, help="also write the EvidenceReport JSON sidecar to this path"
    )
    ev_cmd.add_argument(
        "--format",
        choices=["pdf", "json"],
        default="pdf",
        help="output format (json needs no fpdf2)",
    )
    ev_cmd.set_defaults(func=_evidence)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
