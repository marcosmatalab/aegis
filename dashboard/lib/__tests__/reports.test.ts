import { promises as fs } from "node:fs";
import os from "node:os";
import path from "node:path";

import { afterEach, describe, expect, it } from "vitest";

import calibFix from "../../fixtures/sample-calibration.json";
import evalFix from "../../fixtures/sample-eval.json";
import evidenceFix from "../../fixtures/sample-evidence.json";
import redteamFix from "../../fixtures/sample-redteam.json";
import { loadDashboard } from "../reports";

const ORIG = process.env.AEGIS_REPORTS_DIR;

afterEach(() => {
  if (ORIG === undefined) delete process.env.AEGIS_REPORTS_DIR;
  else process.env.AEGIS_REPORTS_DIR = ORIG;
});

async function tmpReports(files: Record<string, unknown>): Promise<string> {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "aegis-rep-"));
  for (const [name, data] of Object.entries(files)) {
    await fs.writeFile(path.join(dir, name), JSON.stringify(data), "utf8");
  }
  return dir;
}

describe("loadDashboard", () => {
  it("reads and parses the real report files from the dir", async () => {
    process.env.AEGIS_REPORTS_DIR = await tmpReports({
      "eval-golden.json": evalFix,
      "redteam-redteam.json": redteamFix,
      "calibration.json": calibFix,
      "evidence-golden.json": evidenceFix,
    });
    const d = await loadDashboard();
    expect(d.evalView?.judge).toBe("geval");
    expect(d.evalRuns).toHaveLength(1);
    expect(d.redteam?.overallDetectionRate).toBe(0.72);
    expect(d.calibration?.global?.kappa).toBe(0.933);
    expect(d.evidence?.summaryCounts.partial).toBe(5);
  });

  it("picks the newest eval run by created", async () => {
    process.env.AEGIS_REPORTS_DIR = await tmpReports({
      "eval-a.json": { ...evalFix, created: 1, suite: "old" },
      "eval-b.json": { ...evalFix, created: 2, suite: "new" },
    });
    const d = await loadDashboard();
    expect(d.evalView?.suite).toBe("new");
    expect(d.evalRuns).toHaveLength(2);
  });

  it("returns all-null (never throws) when the dir is missing", async () => {
    process.env.AEGIS_REPORTS_DIR = path.join(os.tmpdir(), "aegis-missing-xyz-zzz");
    const d = await loadDashboard();
    expect(d.evalView).toBeNull();
    expect(d.redteam).toBeNull();
    expect(d.calibration).toBeNull();
    expect(d.evidence).toBeNull();
    expect(d.evalRuns).toEqual([]);
  });

  it("treats a present-but-corrupt file as absent (never throws)", async () => {
    const dir = await fs.mkdtemp(path.join(os.tmpdir(), "aegis-rep-"));
    await fs.writeFile(path.join(dir, "calibration.json"), "{not json", "utf8");
    process.env.AEGIS_REPORTS_DIR = dir;
    const d = await loadDashboard();
    expect(d.calibration).toBeNull();
  });
});
