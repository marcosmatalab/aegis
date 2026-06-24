import { describe, expect, it } from "vitest";

import sampleCalibration from "../../fixtures/sample-calibration.json";
import sampleEval from "../../fixtures/sample-eval.json";
import sampleEvidence from "../../fixtures/sample-evidence.json";
import sampleRedteam from "../../fixtures/sample-redteam.json";
import { parseCalibration } from "../parse/calibration";
import { parseEval } from "../parse/eval";
import { parseEvidence } from "../parse/evidence";
import { parseRedteam } from "../parse/redteam";

function present<T>(x: T | null): T {
  expect(x).not.toBeNull();
  return x as T;
}

describe("parseEval", () => {
  it("preserves CLEAR status verbatim and keeps placeholder values null (never 0)", () => {
    const v = present(parseEval(sampleEval));
    expect(v.judge).toBe("geval");
    expect(v.judgeIsMock).toBe(false);
    expect(v.clear.map((d) => d.name)).toEqual([
      "cost",
      "latency",
      "efficiency",
      "accuracy",
      "reliability",
    ]);
    const cost = present(v.clear.find((d) => d.name === "cost") ?? null);
    expect(cost.status).toBe("placeholder"); // verbatim, never laundered
    expect(cost.value).toBeNull(); // placeholder => absent, not 0
    expect(v.clear.find((d) => d.name === "accuracy")?.status).toBe("measured");
    expect(v.levels.map((l) => l.level)).toEqual(["L1", "L2", "L3"]);
  });

  it("flags a mock judge", () => {
    expect(present(parseEval({ ...sampleEval, judge: "mock" })).judgeIsMock).toBe(true);
  });

  it("returns null for a non-object", () => {
    expect(parseEval(null)).toBeNull();
    expect(parseEval([1, 2])).toBeNull();
    expect(parseEval("nope")).toBeNull();
  });

  it("degrades missing/null nested fields to absent, never crashing", () => {
    const v = present(
      parseEval({ judge: "geval", levels: null, clear: null, overall_score: null }),
    );
    expect(v.levels).toEqual([]);
    expect(v.clear).toEqual([]);
    expect(v.overallScore).toBeNull();
  });

  it("keeps a non-numeric score as null (never a fabricated number)", () => {
    const v = present(parseEval({ clear: { accuracy: { status: "measured", value: "oops" } } }));
    expect(v.clear[0].value).toBeNull();
  });
});

describe("parseRedteam", () => {
  it("surfaces named gaps and per-category detection verbatim", () => {
    const v = present(parseRedteam(sampleRedteam));
    expect(v.overallDetectionRate).toBe(0.72);
    expect(v.knownGaps).toHaveLength(2);
    expect(v.knownGaps[0].gapReason).toContain("leetspeak");
    expect(v.categories.find((c) => c.category === "prompt_injection")?.detectionRate).toBe(0.636);
  });

  it("is null-safe on a null category value and non-dict gap elements", () => {
    const v = present(
      parseRedteam({ categories: { x: null }, known_gaps: [null, "bad"], overall: null }),
    );
    expect(v.categories[0].detectionRate).toBeNull();
    expect(v.knownGaps).toEqual([]); // non-dict gaps dropped, never crashed
    expect(v.overallDetectionRate).toBeNull();
  });
});

describe("parseCalibration", () => {
  it("parses kappa + matrix + per-criterion sections", () => {
    const v = present(parseCalibration(sampleCalibration));
    expect(v.global?.kappa).toBe(0.933);
    expect(v.global?.matrix?.humanFailJudgePass).toBe(1);
    expect(v.perCriterion.map((c) => c.criterion)).toEqual(["relevancy", "faithfulness"]);
  });

  it("keeps an undefined kappa null (degenerate table), never 0", () => {
    const v = present(
      parseCalibration({ judge: "geval", global: { kappa: null, band: "undefined", n_valid: 0 } }),
    );
    expect(v.global?.kappa).toBeNull();
    expect(v.global?.band).toBe("undefined");
  });
});

describe("parseEvidence", () => {
  it("preserves statuses verbatim + counts + disclaimer", () => {
    const v = present(parseEvidence(sampleEvidence));
    expect(v.summaryCounts).toEqual({ covered: 3, partial: 5, not_covered: 3, out_of_scope: 3 });
    expect(v.controls.find((c) => c.controlId === "MEASURE 2.6")?.status).toBe("partial");
    expect(v.controls.some((c) => c.status === "out_of_scope")).toBe(true);
    expect(v.disclaimer).toContain("PARTIAL TECHNICAL EVIDENCE");
  });

  it("is null-safe on non-dict control elements and missing counts", () => {
    const v = present(parseEvidence({ controls: [null, "x"], summary_counts: null }));
    expect(v.controls).toEqual([]);
    expect(v.summaryCounts).toEqual({ covered: 0, partial: 0, not_covered: 0, out_of_scope: 0 });
  });
});
