// SERVER-ONLY read-only data source. Reads the REAL reports directory from the local
// filesystem at request time and parses each report via the pure parsers. It NEVER
// calls the gateway/provider/model, makes no network request, and writes nothing.
// A missing/unreadable file degrades to null (an absent panel) — never a throw.
//
// The dir is `AEGIS_REPORTS_DIR` if set, else `../reports` relative to the dashboard
// process cwd (i.e. the repo's reports/ when run from dashboard/). Filenames are
// discovered from the dir listing, never taken from request input (no path traversal).

import { promises as fs } from "node:fs";
import path from "node:path";

import { parseCalibration } from "./parse/calibration";
import { parseEval } from "./parse/eval";
import { parseEvidence } from "./parse/evidence";
import { parseRedteam } from "./parse/redteam";
import type { CalibrationView, EvalView, EvidenceView, RedteamView } from "./types";

export function reportsDir(): string {
  const env = process.env.AEGIS_REPORTS_DIR;
  return env && env.trim() ? path.resolve(env) : path.resolve(process.cwd(), "..", "reports");
}

async function readJson(file: string): Promise<unknown> {
  try {
    return JSON.parse(await fs.readFile(file, "utf8"));
  } catch {
    return null; // absent OR unreadable/corrupt -> absent (honest, never a crash)
  }
}

async function listJson(dir: string, prefix: string): Promise<string[]> {
  try {
    const entries = await fs.readdir(dir);
    return entries
      .filter((f) => f.startsWith(prefix) && f.endsWith(".json"))
      .map((f) => path.join(dir, f));
  } catch {
    return [];
  }
}

async function newestOf<T>(
  dir: string,
  prefix: string,
  parse: (raw: unknown) => T | null,
  createdOf: (view: T) => number | null,
): Promise<T | null> {
  const files = await listJson(dir, prefix);
  const views = (await Promise.all(files.map((f) => readJson(f))))
    .map((raw) => parse(raw))
    .filter((v): v is T => v !== null);
  if (views.length === 0) return null;
  views.sort((a, b) => (createdOf(b) ?? 0) - (createdOf(a) ?? 0));
  return views[0];
}

export interface EvalRun {
  file: string;
  view: EvalView;
}

export interface DashboardData {
  reportsDir: string;
  evalView: EvalView | null;
  evalRuns: EvalRun[]; // every eval-*.json, newest first — for trends + the runs list
  redteam: RedteamView | null;
  calibration: CalibrationView | null;
  evidence: EvidenceView | null;
}

export async function loadDashboard(): Promise<DashboardData> {
  const dir = reportsDir();

  const evalFiles = await listJson(dir, "eval-");
  const evalRuns: EvalRun[] = (
    await Promise.all(
      evalFiles.map(async (file) => ({ file, view: parseEval(await readJson(file)) })),
    )
  )
    .filter((r): r is EvalRun => r.view !== null)
    .sort((a, b) => (b.view.created ?? 0) - (a.view.created ?? 0));

  return {
    reportsDir: dir,
    evalView: evalRuns[0]?.view ?? null,
    evalRuns,
    redteam: await newestOf(dir, "redteam-", parseRedteam, (v) => v.created),
    calibration: parseCalibration(await readJson(path.join(dir, "calibration.json"))),
    evidence: await newestOf(dir, "evidence-", parseEvidence, (v) => v.generated),
  };
}
