"""Aegis command-line interface (stdlib argparse, no extra deps).

Subcommands:
  ``aegis eval run`` — run the eval suite over a golden set (L1/L2/L3 + F4
  trajectory metrics, the Agent-as-a-Judge, and the CLEAR dimensions) and write a
  JSON report.

The ``--fail-under`` CI gate is an inert seam: it only affects the exit code when
explicitly passed. The real, baseline-comparing CI gate is a later phase (F7).
"""

from __future__ import annotations

import argparse
import sys
import time

from aegis.evals.dataset import DEFAULT_GOLDEN_PATH, GoldenDatasetError, load_golden
from aegis.evals.judge.agent import build_trajectory_judge
from aegis.evals.judge.factory import build_judge
from aegis.evals.judge.geval import JudgeNotConfiguredError
from aegis.evals.persistence import DEFAULT_REPORTS_DIR, write_report
from aegis.evals.runner import run_suite
from aegis.gateway.config import get_settings
from aegis.gateway.errors import ProviderNotConfiguredError

_CLEAR_ORDER = ("cost", "latency", "efficiency", "accuracy", "reliability")


def _format_clear(dim: dict) -> str:
    """Compact one-token rendering of a CLEAR dimension, marking synthetic data."""
    if not dim["applicable"]:
        return f"{dim['name']}=n/a({dim['status']})"
    if dim["score"] is not None:
        suffix = "" if dim["status"] == "measured" else f"({dim['status']})"
        return f"{dim['name']}={dim['score']:.3f}{suffix}"
    return f"{dim['name']}={dim['value']:.3g}{dim['unit']}({dim['status']})"


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
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
