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
export const dynamic = "force-dynamic";

export default async function Page() {
  const data = await loadDashboard();
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
      <DashboardHeader reportsDir={data.reportsDir} />

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
