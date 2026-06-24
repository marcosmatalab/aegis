import { fmtUnixUtc } from "./format";
import type { EvalRun } from "./reports";

// One point per REAL eval run (never an invented/interpolated point). A run with a
// null metric stays null -> the chart leaves a gap (connectNulls=false), never a
// fabricated value. A trend is only meaningful with >= 2 runs (the chart enforces it).
export interface TrendPoint {
  created: number | null;
  label: string;
  overall: number | null;
  l1: number | null;
  l2: number | null;
  l3: number | null;
}

function levelMean(run: EvalRun, level: string): number | null {
  return run.view.levels.find((l) => l.level === level)?.meanScore ?? null;
}

/** Build the eval trend series, sorted oldest -> newest by `created`. */
export function evalTrend(runs: EvalRun[]): TrendPoint[] {
  return [...runs]
    .sort((a, b) => (a.view.created ?? 0) - (b.view.created ?? 0))
    .map((r) => ({
      created: r.view.created,
      label: r.view.created === null ? "?" : fmtUnixUtc(r.view.created).slice(0, 10),
      overall: r.view.overallScore,
      l1: levelMean(r, "L1"),
      l2: levelMean(r, "L2"),
      l3: levelMean(r, "L3"),
    }));
}
