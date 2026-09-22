import { AbsentPanel } from "@/components/AbsentPanel";
import { ClearPanel } from "@/components/ClearPanel";
import { DashboardHeader } from "@/components/DashboardHeader";
import { EvalScorecard } from "@/components/EvalScorecard";
import { EvidencePanel } from "@/components/EvidencePanel";
import { KappaPanel } from "@/components/KappaPanel";
import { RedteamPanel } from "@/components/RedteamPanel";
import { RunsList } from "@/components/RunsList";
import { TrendsChart } from "@/components/TrendsChart";
import { loadDashboard } from "@/lib/reports";
import { evalTrend } from "@/lib/trend";

// SERVER component: reads the reports directory at REQUEST time (never bakes a
// build-time snapshot), so a fresh `aegis eval/redteam/evidence` run shows up on
// refresh. It passes DATA + i18n KEYS to client components; it renders no translatable
// literal text itself, so the i18n hook (a client API) never needs to run here.
//
// Next requires this to be a statically-parsable literal, so it cannot be branched
// on an env var. The GitHub Pages export flips it to "force-static" via
// scripts/prepare-static-export.mjs, which is a deliberate, visible build step
// rather than a hidden conditional.
export const dynamic = "force-dynamic";

// On the published Pages build, the reports directory is an absolute path on a CI
// runner: meaningless to a visitor, and a needless leak of the build environment.
// Show what the data IS instead of where it happened to sit.
const SNAPSHOT_SOURCE = "dashboard/sample-reports/ (committed output of a real run)";

export default async function Page() {
  const isSnapshot = process.env.AEGIS_STATIC_EXPORT === "1";
  const loaded = await loadDashboard();
  // Normalise ONCE, here, rather than at each consumer: RunsList renders both the
  // directory and each run's path, and a second place to forget is a second way to
  // leak the CI runner's filesystem into a public page. Each run keeps its file
  // NAME, which is the only part a reader gets anything from.
  const data = isSnapshot
    ? {
        ...loaded,
        reportsDir: SNAPSHOT_SOURCE,
        evalRuns: loaded.evalRuns.map((run) => ({
          ...run,
          file: run.file.replaceAll("\\", "/").split("/").pop() ?? run.file,
        })),
      }
    : loaded;
  return (
    <main
      style={{
        padding: "2rem",
        maxWidth: 1000,
        margin: "0 auto",
        display: "grid",
        gap: "1.25rem",
      }}
    >
      <DashboardHeader reportsDir={data.reportsDir} isSnapshot={isSnapshot} />

      {data.evalView ? (
        <>
          <EvalScorecard view={data.evalView} />
          <ClearPanel dims={data.evalView.clear} />
        </>
      ) : (
        <AbsentPanel
          titleKey="eval.absentTitle"
          reasonKey="absent.evalReason"
          command="aegis eval run"
        />
      )}

      <TrendsChart points={evalTrend(data.evalRuns)} />

      {data.redteam ? (
        <RedteamPanel view={data.redteam} />
      ) : (
        <AbsentPanel
          titleKey="redteam.title"
          reasonKey="absent.redteamReason"
          command="aegis redteam run"
        />
      )}

      {data.calibration ? (
        <KappaPanel view={data.calibration} />
      ) : (
        <AbsentPanel
          titleKey="kappa.title"
          reasonKey="absent.calibrationReason"
          command="aegis calibrate --judge geval"
        />
      )}

      {data.evidence ? (
        <EvidencePanel view={data.evidence} />
      ) : (
        <AbsentPanel
          titleKey="evidence.title"
          reasonKey="absent.evidenceReason"
          command="aegis evidence"
        />
      )}

      <RunsList data={data} />
    </main>
  );
}
