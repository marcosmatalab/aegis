import { fmtNum, fmtUnixUtc } from "@/lib/format";
import type { DashboardData } from "@/lib/reports";
import { Card } from "./Card";

function basename(file: string): string {
  return file.split(/[\\/]/).pop() ?? file;
}

export function RunsList({ data }: { data: DashboardData }) {
  const present: [string, boolean][] = [
    ["eval", data.evalRuns.length > 0],
    ["red-team", data.redteam !== null],
    ["calibration", data.calibration !== null],
    ["evidence", data.evidence !== null],
  ];
  return (
    <Card title="Runs & reports" subtitle={data.reportsDir}>
      <p style={{ margin: "0 0 0.5rem", fontSize: 13, color: "#9aa0aa" }}>
        {present.map(([name, ok]) => `${name}: ${ok ? "present" : "absent"}`).join("  ·  ")}
      </p>
      {data.evalRuns.length === 0 ? (
        <p style={{ margin: 0, color: "#9aa0aa", fontSize: 13 }}>No eval runs in this directory.</p>
      ) : (
        <ul style={{ margin: 0, paddingLeft: "1.1rem", fontSize: 13 }}>
          {data.evalRuns.map((r) => (
            <li key={r.file} style={{ marginBottom: 2 }}>
              <code>{basename(r.file)}</code> — overall {fmtNum(r.view.overallScore)} ·{" "}
              {fmtUnixUtc(r.view.created)}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
