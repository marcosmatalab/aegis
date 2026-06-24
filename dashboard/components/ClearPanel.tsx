import { fmtNum } from "@/lib/format";
import type { ClearDimView } from "@/lib/types";
import { Card } from "./Card";
import { StatusBadge } from "./StatusBadge";

const CAVEAT =
  "Cost/Latency are only real with OpenTelemetry telemetry (F1.x); on the offline mock suite they stay placeholder/synthetic — shown verbatim, never as a measured number.";

export function ClearPanel({ dims }: { dims: ClearDimView[] }) {
  return (
    <Card title="CLEAR" caveat={CAVEAT}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "#9aa0aa" }}>
            <th style={{ padding: "2px 8px 2px 0" }}>Dimension</th>
            <th style={{ padding: "2px 8px" }}>Status</th>
            <th style={{ padding: "2px 8px" }}>Value</th>
            <th style={{ padding: "2px 0" }}>Basis</th>
          </tr>
        </thead>
        <tbody>
          {dims.map((d) => (
            <tr key={d.name} style={{ borderTop: "1px solid #22262e" }}>
              <td style={{ padding: "4px 8px 4px 0" }}>{d.name}</td>
              <td style={{ padding: "4px 8px" }}>
                <StatusBadge status={d.status} />
              </td>
              {/* A non-measured value carries its provenance on the number itself
                  (mirrors the CLI's `0.012usd(estimated)`), and is muted — so an
                  estimated/synthetic/placeholder number never reads as a confident
                  measurement, not even before the eye reaches the badge. */}
              <td
                style={{
                  padding: "4px 8px",
                  color: d.status === "measured" ? undefined : "#9aa0aa",
                }}
              >
                {d.applicable ? (
                  <>
                    {fmtNum(d.score ?? d.value)}
                    {d.unit && d.value !== null ? ` ${d.unit}` : ""}
                    {d.status === "measured" ? "" : ` (${d.status})`}
                  </>
                ) : (
                  "n/a"
                )}
              </td>
              <td style={{ padding: "4px 0", color: "#9aa0aa", fontSize: 12.5 }}>
                {d.basis ?? ""}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
