import { describe, expect, it } from "vitest";

import { type Dict, en, es, lookup, translate } from "../dictionaries";

/** Flatten a nested dict to the set of its dot-path leaf keys. */
function leafPaths(obj: Record<string, unknown>, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([k, v]) => {
    const path = prefix ? `${prefix}.${k}` : k;
    return typeof v === "object" && v !== null
      ? leafPaths(v as Record<string, unknown>, path)
      : [path];
  });
}

describe("dictionaries", () => {
  it("en and es have EXACTLY the same key set (fails if they diverge)", () => {
    const enKeys = leafPaths(en).sort();
    const esKeys = leafPaths(es).sort();
    expect(esKeys).toEqual(enKeys);
  });

  it("every leaf in both locales is a non-empty string", () => {
    for (const dict of [en, es]) {
      for (const path of leafPaths(dict)) {
        expect(typeof lookup(dict, path)).toBe("string");
        expect(lookup(dict, path)?.length).toBeGreaterThan(0);
      }
    }
  });

  it("does NOT contain any verbatim report status enum as a value (honesty guard)", () => {
    const verbatim = new Set([
      "measured",
      "estimated",
      "synthetic",
      "placeholder",
      "covered",
      "partial",
      "not_covered",
      "out_of_scope",
    ]);
    for (const dict of [en, es]) {
      for (const path of leafPaths(dict)) {
        expect(verbatim.has(lookup(dict, path) ?? "")).toBe(false);
      }
    }
  });
});

describe("translate", () => {
  it("returns the per-locale string", () => {
    expect(translate(en, en, "eval.title")).toBe("Evaluation (L1/L2/L3)");
    expect(translate(es, en, "eval.title")).toBe("Evaluación (L1/L2/L3)");
    expect(translate(es, en, "redteam.gotThrough")).toBe("Se colaron");
  });

  it("falls back to English when the key is missing in the primary locale", () => {
    const empty = {} as unknown as Dict;
    expect(translate(empty, en, "eval.title")).toBe("Evaluation (L1/L2/L3)");
  });

  it("falls back to the key itself when missing everywhere", () => {
    const empty = {} as unknown as Dict;
    expect(translate(es, en, "nope.missing.key")).toBe("nope.missing.key");
    expect(translate(empty, empty, "also.missing")).toBe("also.missing");
  });

  it("interpolates {vars}", () => {
    expect(translate(en, en, "trends.runsSubtitle", { n: 4 })).toBe("4 runs");
    expect(translate(es, en, "redteam.namedGaps", { count: 7 })).toBe(
      "Brechas conocidas (7) — se cuelan por diseño",
    );
    // an unknown var is left as a visible {placeholder}, never blank
    expect(translate(en, en, "trends.runsSubtitle", {})).toBe("{n} runs");
  });
});
