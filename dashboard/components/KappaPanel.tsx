import { fmtInt, fmtNum } from "@/lib/format";
import type { CalibrationView, KappaSectionView } from "@/lib/types";
import { Card } from "./Card";

const CAVEAT =
  "Cohen's κ is DIRECTIONAL — agreement with one annotator's rubric (small N), not ground truth. Landis-Koch bands are arbitrary conventions; a degenerate table yields an undefined κ (shown as 'undefined', never 0).";
const MOCK_CAVEAT =
  "judge=mock — a wiring smoke test (κ of the heuristic mock vs the labels), not a real-judge calibration";

function kappaText(s: KappaSectionView): string {
  // null kappa = undefined (degenerate agreement table) — never rendered as a number
  const k = s.kappa === null ? "undefined" : fmtNum(s.kappa);
  return `${k} (${s.band ?? "—"})`;
}

function SectionRow({ label, s }: { label: string; s: KappaSectionView }) {
  return (
    <tr style={{ borderTop: "1px solid #22262e" }}>
      <td style={{ padding: "4px 8px 4px 0" }}>{label}</td>
      <td style={{ padding: "4px 8px" }}>{kappaText(s)}</td>
      <td style={{ padding: "4px 8px" }}>{fmtNum(s.pO, 3)}</td>
      <td style={{ padding: "4px 0" }}>{fmtInt(s.nValid)}</td>
    </tr>
  );
}

export function KappaPanel({ view }: { view: CalibrationView }) {
  const m = view.global?.matrix ?? null;
  return (
    <Card
      title="Judge calibration (Cohen's κ)"
      subtitle={`judge=${view.judge ?? "—"} · n=${fmtInt(view.nCases)} · parse-failed=${fmtInt(view.nParseFailed)}`}
      caveat={view.judgeIsMock ? `${MOCK_CAVEAT}. ${CAVEAT}` : CAVEAT}
    >
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "#9aa0aa" }}>
            <th style={{ padding: "2px 8px 2px 0" }}>Scope</th>
            <th style={{ padding: "2px 8px" }}>κ (band)</th>
            <th style={{ padding: "2px 8px" }}>p_o</th>
            <th style={{ padding: "2px 0" }}>n</th>
          </tr>
        </thead>
        <tbody>
          {view.global ? <SectionRow label="global" s={view.global} /> : null}
          {view.perCriterion.map((c) => (
            <SectionRow key={c.criterion} label={c.criterion} s={c.section} />
          ))}
        </tbody>
      </table>

      {m ? (
        <>
          <h3 style={{ margin: "0.9rem 0 0.35rem", fontSize: 14 }}>Global confusion matrix</h3>
          <p style={{ margin: "0 0 0.35rem", color: "#9aa0aa", fontSize: 12 }}>
            {m.orientation ?? "rows=human, cols=judge; positive='pass'"}
          </p>
          <table style={{ borderCollapse: "collapse", fontSize: 13 }}>
            <tbody>
              <tr>
                <td style={cell}>human pass / judge pass: {fmtInt(m.humanPassJudgePass)}</td>
                <td style={cell}>human pass / judge fail: {fmtInt(m.humanPassJudgeFail)}</td>
              </tr>
              <tr>
                <td style={cell}>human fail / judge pass: {fmtInt(m.humanFailJudgePass)}</td>
                <td style={cell}>human fail / judge fail: {fmtInt(m.humanFailJudgeFail)}</td>
              </tr>
            </tbody>
          </table>
        </>
      ) : null}
    </Card>
  );
}

const cell = { border: "1px solid #2c313a", padding: "4px 8px" } as const;
