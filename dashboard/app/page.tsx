import { AbsentPanel } from "@/components/AbsentPanel";
import { ClearPanel } from "@/components/ClearPanel";
import { EvalScorecard } from "@/components/EvalScorecard";
import { EvidencePanel } from "@/components/EvidencePanel";
import { KappaPanel } from "@/components/KappaPanel";
import { RedteamPanel } from "@/components/RedteamPanel";
import { RunsList } from "@/components/RunsList";
import { TrendsChart } from "@/components/TrendsChart";
import { loadDashboard } from "@/lib/reports";
import { evalTrend } from "@/lib/trend";

// Read the reports directory at REQUEST time (never bake a build-time snapshot), so a
// fresh `aegis eval/redteam/evidence` run shows up on refresh.
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
      <header>
        <h1 style={{ margin: 0 }}>🛡️ Aegis dashboard</h1>
        <p style={{ color: "#9aa0aa", margin: "0.35rem 0 0", fontSize: 13 }}>
          Read-only view of the real reports in <code>{data.reportsDir}</code>. Statuses and caveats
          are shown verbatim; absent reports are marked, never faked.
        </p>
      </header>

      {data.evalView ? (
        <>
          <EvalScorecard view={data.evalView} />
          <ClearPanel dims={data.evalView.clear} />
        </>
      ) : (
        <AbsentPanel
          title="Evaluation (L1/L2/L3) + CLEAR"
          reason="no eval-*.json in the reports directory"
          hint="run: aegis eval run"
        />
      )}

      <TrendsChart points={evalTrend(data.evalRuns)} />

      {data.redteam ? (
        <RedteamPanel view={data.redteam} />
      ) : (
        <AbsentPanel
          title="Red-team (OWASP)"
          reason="no redteam-*.json in the reports directory"
          hint="run: aegis redteam run"
        />
      )}

      {data.calibration ? (
        <KappaPanel view={data.calibration} />
      ) : (
        <AbsentPanel
          title="Judge calibration (Cohen's κ)"
          reason="no calibration.json in the reports directory"
          hint="run: aegis calibrate --judge geval"
        />
      )}

      {data.evidence ? (
        <EvidencePanel view={data.evidence} />
      ) : (
        <AbsentPanel
          title="Governance evidence (F8)"
          reason="no evidence-*.json in the reports directory"
          hint="run: aegis evidence"
        />
      )}

      <RunsList data={data} />
    </main>
  );
}
