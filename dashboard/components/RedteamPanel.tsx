import { fmtInt, fmtPct } from "@/lib/format";
import type { RedteamView } from "@/lib/types";
import { Card } from "./Card";

const CAVEAT =
  "Detection rate is DIRECTIONAL coverage-against-the-catalog, not a pass/fail compliance number. 'Got through' counts attacks that BYPASSED the guardrails (a miss — higher is worse), not test passes. The named gaps below get through by design and are disclosed, not hidden.";

export function RedteamPanel({ view }: { view: RedteamView }) {
  return (
    <Card
      title="Red-team (OWASP)"
      subtitle={`${fmtInt(view.caseCount)} attacks · overall detection ${fmtPct(view.overallDetectionRate)}`}
      caveat={CAVEAT}
    >
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "#9aa0aa" }}>
            <th style={{ padding: "2px 8px 2px 0" }}>Category</th>
            <th style={{ padding: "2px 8px" }}>OWASP</th>
            <th style={{ padding: "2px 8px" }}>Detection</th>
            {/* attacks that BYPASSED the guardrails — a miss, NOT a test pass */}
            <th style={{ padding: "2px 0" }}>Got through</th>
          </tr>
        </thead>
        <tbody>
          {view.categories.map((c) => (
            <tr key={c.category} style={{ borderTop: "1px solid #22262e" }}>
              <td style={{ padding: "4px 8px 4px 0" }}>{c.category}</td>
              <td style={{ padding: "4px 8px", color: "#9aa0aa" }}>{c.owasp ?? "—"}</td>
              <td style={{ padding: "4px 8px" }}>{fmtPct(c.detectionRate)}</td>
              {/* warn tone: a non-zero "got through" is a bad outcome, never success-coloured */}
              <td style={{ padding: "4px 0", color: c.passed ? "#e0b15e" : "#9aa0aa" }}>
                {fmtInt(c.passed)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3 style={{ margin: "0.9rem 0 0.35rem", fontSize: 14 }}>
        Named gaps ({view.knownGaps.length}) — get through by design
      </h3>
      {view.knownGaps.length === 0 ? (
        <p style={{ margin: 0, color: "#9aa0aa", fontSize: 13 }}>none in this run</p>
      ) : (
        <ul style={{ margin: 0, paddingLeft: "1.1rem", fontSize: 13 }}>
          {view.knownGaps.map((g) => (
            <li key={g.id} style={{ marginBottom: 2 }}>
              <code>{g.id}</code> <span style={{ color: "#9aa0aa" }}>[{g.category ?? "?"}]</span>
              {g.gapReason ? ` — ${g.gapReason}` : ""}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
