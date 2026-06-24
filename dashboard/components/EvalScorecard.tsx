import { fmtInt, fmtNum, fmtUnixUtc } from "@/lib/format";
import type { EvalView } from "@/lib/types";
import { Card } from "./Card";

const MOCK_CAVEAT =
  "judge=mock — a deterministic wiring smoke test (L2 by the heuristic judge), not a real-judge evaluation";

export function EvalScorecard({ view }: { view: EvalView }) {
  return (
    <Card
      title="Evaluation (L1/L2/L3)"
      subtitle={`suite=${view.suite ?? "—"} · judge=${view.judge ?? "—"} · ${fmtInt(view.caseCount)} cases · ${fmtUnixUtc(view.created)}`}
      caveat={view.judgeIsMock ? MOCK_CAVEAT : undefined}
    >
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "#9aa0aa" }}>
            <th style={{ padding: "2px 0" }}>Level</th>
            <th>Mean</th>
            <th>Passed</th>
          </tr>
        </thead>
        <tbody>
          {view.levels.map((l) => (
            <tr key={l.level}>
              <td style={{ padding: "2px 0" }}>{l.level}</td>
              <td>{fmtNum(l.meanScore)}</td>
              <td>
                {fmtInt(l.passed)}/{fmtInt(l.scored)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p style={{ margin: "0.75rem 0 0", fontSize: 15 }}>
        overall = <strong>{fmtNum(view.overallScore)}</strong>
      </p>
    </Card>
  );
}
