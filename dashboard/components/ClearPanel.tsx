"use client";

import { fmtNum } from "@/lib/format";
import { useLocale } from "@/lib/i18n/LocaleProvider";
import type { ClearDimView } from "@/lib/types";
import { Card } from "./Card";
import { StatusBadge } from "./StatusBadge";

export function ClearPanel({ dims }: { dims: ClearDimView[] }) {
  const { t } = useLocale();
  return (
    <Card title={t("clear.title")} caveat={t("clear.caveat")}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "#9aa0aa" }}>
            <th style={{ padding: "2px 8px 2px 0" }}>{t("clear.colDimension")}</th>
            <th style={{ padding: "2px 8px" }}>{t("clear.colStatus")}</th>
            <th style={{ padding: "2px 8px" }}>{t("clear.colValue")}</th>
            <th style={{ padding: "2px 0" }}>{t("clear.colBasis")}</th>
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
                  (the VERBATIM status, e.g. `(estimated)`, mirroring the CLI), and is
                  muted — so it never reads as a confident measurement. The status enum
                  is never translated. */}
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
                  t("clear.na")
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
