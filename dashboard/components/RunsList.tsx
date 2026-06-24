"use client";

import { fmtNum, fmtUnixUtc } from "@/lib/format";
import { useLocale } from "@/lib/i18n/LocaleProvider";
import type { DashboardData } from "@/lib/reports";
import { Card } from "./Card";

function basename(file: string): string {
  return file.split(/[\\/]/).pop() ?? file;
}

export function RunsList({ data }: { data: DashboardData }) {
  const { t } = useLocale();
  const present: [string, boolean][] = [
    [t("runs.kindEval"), data.evalRuns.length > 0],
    [t("runs.kindRedteam"), data.redteam !== null],
    [t("runs.kindCalibration"), data.calibration !== null],
    [t("runs.kindEvidence"), data.evidence !== null],
  ];
  return (
    <Card title={t("runs.title")} subtitle={data.reportsDir}>
      <p style={{ margin: "0 0 0.5rem", fontSize: 13, color: "#9aa0aa" }}>
        {present
          .map(([name, ok]) => `${name}: ${ok ? t("runs.present") : t("runs.absent")}`)
          .join("  ·  ")}
      </p>
      {data.evalRuns.length === 0 ? (
        <p style={{ margin: 0, color: "#9aa0aa", fontSize: 13 }}>{t("runs.noEvalRuns")}</p>
      ) : (
        <ul style={{ margin: 0, paddingLeft: "1.1rem", fontSize: 13 }}>
          {data.evalRuns.map((r) => (
            <li key={r.file} style={{ marginBottom: 2 }}>
              <code>{basename(r.file)}</code> — {t("runs.overall")} {fmtNum(r.view.overallScore)} ·{" "}
              {fmtUnixUtc(r.view.created)}
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
