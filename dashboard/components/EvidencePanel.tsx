import type { EvidenceView } from "@/lib/types";
import { Card } from "./Card";
import { StatusBadge } from "./StatusBadge";

export function EvidencePanel({ view }: { view: EvidenceView }) {
  const c = view.summaryCounts;
  return (
    <Card
      title="Governance evidence (F8)"
      subtitle={`covered=${c.covered} · partial=${c.partial} · not_covered=${c.not_covered} · out_of_scope=${c.out_of_scope}`}
      caveat="Counts are over the small set of mapped technical controls — NOT a coverage percentage; most framework clauses are out of scope."
    >
      {view.disclaimer ? (
        <p style={{ margin: "0 0 0.75rem", color: "#9aa0aa", fontSize: 12.5 }}>{view.disclaimer}</p>
      ) : null}
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13.5 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "#9aa0aa" }}>
            <th style={{ padding: "2px 8px 2px 0" }}>Control</th>
            <th style={{ padding: "2px 8px" }}>Status</th>
            <th style={{ padding: "2px 0" }}>Evidence</th>
          </tr>
        </thead>
        <tbody>
          {view.controls.map((ctrl) => (
            <tr
              key={`${ctrl.framework}:${ctrl.controlId}`}
              style={{ borderTop: "1px solid #22262e" }}
            >
              <td style={{ padding: "4px 8px 4px 0", verticalAlign: "top" }}>
                <strong>{ctrl.controlId}</strong>
                <div style={{ color: "#9aa0aa", fontSize: 12 }}>{ctrl.framework}</div>
              </td>
              <td style={{ padding: "4px 8px", verticalAlign: "top" }}>
                <StatusBadge status={ctrl.status} />
              </td>
              <td style={{ padding: "4px 0", verticalAlign: "top" }}>
                {ctrl.derivedValue ?? ""}
                {ctrl.caveat ? (
                  <div style={{ color: "#e0b15e", fontSize: 12 }}>⚠ {ctrl.caveat}</div>
                ) : null}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
