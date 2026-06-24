import { describe, expect, it } from "vitest";

import type { EvalRun } from "../reports";
import { evalTrend } from "../trend";

function run(created: number | null, overall: number | null, l1: number | null): EvalRun {
  return {
    file: `eval-${created}.json`,
    view: {
      suite: "s",
      judge: "geval",
      judgeIsMock: false,
      caseCount: 1,
      created,
      overallScore: overall,
      levels: l1 === null ? [] : [{ level: "L1", meanScore: l1, passed: null, scored: null }],
      clear: [],
      trajectory: [],
    },
  };
}

describe("evalTrend", () => {
  it("orders points oldest -> newest and extracts metrics", () => {
    const points = evalTrend([run(2, 0.9, 0.8), run(1, 0.7, 0.6)]);
    expect(points.map((p) => p.created)).toEqual([1, 2]);
    expect(points[0].overall).toBe(0.7);
    expect(points[1].l1).toBe(0.8);
  });

  it("keeps a missing metric null (a gap, never interpolated/zero-filled)", () => {
    const points = evalTrend([run(1, null, null), run(2, 0.5, null)]);
    expect(points[0].overall).toBeNull();
    expect(points[0].l1).toBeNull(); // no L1 level present -> null, not 0
  });

  it("is empty for no runs (the chart shows an honest absent state)", () => {
    expect(evalTrend([])).toEqual([]);
  });
});
