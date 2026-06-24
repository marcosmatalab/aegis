import type { ClearDimView, EvalView, LevelView, TrajectoryMetricView } from "../types";
import { asArray, asBoolean, asNumber, asObject, asString } from "./raw";

const CLEAR_ORDER = ["cost", "latency", "efficiency", "accuracy", "reliability"];
const LEVELS = ["L1", "L2", "L3"];

function parseClearDim(fallbackName: string, raw: unknown): ClearDimView | null {
  const o = asObject(raw);
  if (!o) return null;
  return {
    name: asString(o.name) ?? fallbackName,
    status: asString(o.status) ?? "unknown", // verbatim; never coerced toward a better status
    applicable: asBoolean(o.applicable),
    score: asNumber(o.score),
    value: asNumber(o.value),
    unit: asString(o.unit),
    basis: asString(o.basis),
  };
}

/** Parse a raw eval report into an EvalView, or null if it is not an object. */
export function parseEval(raw: unknown): EvalView | null {
  const o = asObject(raw);
  if (!o) return null;

  const levelsRaw = asObject(o.levels) ?? {};
  const levels: LevelView[] = [];
  for (const lvl of LEVELS) {
    const lo = asObject(levelsRaw[lvl]);
    if (lo) {
      levels.push({
        level: lvl,
        meanScore: asNumber(lo.mean_score),
        passed: asNumber(lo.passed),
        scored: asNumber(lo.scored),
      });
    }
  }

  const clearRaw = asObject(o.clear) ?? {};
  const clear: ClearDimView[] = [];
  for (const name of CLEAR_ORDER) {
    const dim = parseClearDim(name, clearRaw[name]);
    if (dim) clear.push(dim);
  }

  const trajRaw = asObject(o.trajectory) ?? {};
  const trajectory: TrajectoryMetricView[] = [];
  for (const [metric, v] of Object.entries(trajRaw)) {
    const mo = asObject(v);
    if (mo) {
      trajectory.push({ metric, meanScore: asNumber(mo.mean_score), scored: asNumber(mo.scored) });
    }
  }

  const judge = asString(o.judge);
  return {
    suite: asString(o.suite),
    judge,
    judgeIsMock: judge === "mock",
    caseCount: asNumber(o.case_count),
    created: asNumber(o.created),
    overallScore: asNumber(o.overall_score),
    levels,
    clear,
    trajectory,
  };
}
