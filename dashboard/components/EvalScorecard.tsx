"use client";

import { fmtInt, fmtNum, fmtUnixUtc } from "@/lib/format";
import { useLocale } from "@/lib/i18n/LocaleProvider";
import type { EvalView } from "@/lib/types";
import { Card } from "./Card";

export function EvalScorecard({ view }: { view: EvalView }) {
  const { t } = useLocale();
  return (
    <Card
      title={t("eval.title")}
      subtitle={t("eval.subtitle", {
        suite: view.suite ?? "—",
        judge: view.judge ?? "—",
        n: fmtInt(view.caseCount),
        date: fmtUnixUtc(view.created),
      })}
      caveat={view.judgeIsMock ? t("eval.mockCaveat") : undefined}
    >
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "#9aa0aa" }}>
            <th style={{ padding: "2px 0" }}>{t("eval.colLevel")}</th>
            <th>{t("eval.colMean")}</th>
            <th>{t("eval.colPassed")}</th>
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
        {t("eval.overallLabel")} = <strong>{fmtNum(view.overallScore)}</strong>
      </p>
      {view.trajectory.length > 0 ? (
        <p style={{ margin: "0.5rem 0 0", color: "#9aa0aa", fontSize: 12.5 }}>
          {t("eval.trajectoryLabel")}:{" "}
          {view.trajectory.map((tr) => `${tr.metric}=${fmtNum(tr.meanScore)}`).join("  ·  ")}
        </p>
      ) : null}
    </Card>
  );
}
