"use client";

import { fmtInt, fmtNum } from "@/lib/format";
import { useLocale } from "@/lib/i18n/LocaleProvider";
import type { CalibrationView, KappaSectionView } from "@/lib/types";
import { Card } from "./Card";

function kappaText(s: KappaSectionView): string {
  // null kappa = undefined (degenerate agreement table) — never rendered as a number,
  // and the verbatim "undefined" / band come from the report, so they are NOT translated.
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
  const { t } = useLocale();
  const m = view.global?.matrix ?? null;
  const base = [
    t("kappa.caveatDirectional"),
    t("kappa.caveatSmallN"),
    t("kappa.caveatDegenerate"),
  ].join(" ");
  const caveat = view.judgeIsMock ? `${t("kappa.mockCaveat")}. ${base}` : base;
  return (
    <Card
      title={t("kappa.title")}
      subtitle={t("kappa.subtitle", {
        judge: view.judge ?? "—",
        n: fmtInt(view.nCases),
        pf: fmtInt(view.nParseFailed),
      })}
      caveat={caveat}
    >
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 14 }}>
        <thead>
          <tr style={{ textAlign: "left", color: "#9aa0aa" }}>
            <th style={{ padding: "2px 8px 2px 0" }}>{t("kappa.colScope")}</th>
            <th style={{ padding: "2px 8px" }}>{t("kappa.colKappa")}</th>
            <th style={{ padding: "2px 8px" }}>{t("kappa.colPo")}</th>
            <th style={{ padding: "2px 0" }}>{t("kappa.colN")}</th>
          </tr>
        </thead>
        <tbody>
          {view.global ? <SectionRow label={t("kappa.globalRow")} s={view.global} /> : null}
          {view.perCriterion.map((c) => (
            <SectionRow key={c.criterion} label={c.criterion} s={c.section} />
          ))}
        </tbody>
      </table>

      {m ? (
        <>
          <h3 style={{ margin: "0.9rem 0 0.35rem", fontSize: 14 }}>{t("kappa.matrixTitle")}</h3>
          <p style={{ margin: "0 0 0.35rem", color: "#9aa0aa", fontSize: 12 }}>
            {m.orientation ?? t("kappa.matrixOrientationDefault")}
          </p>
          <table style={{ borderCollapse: "collapse", fontSize: 13 }}>
            <tbody>
              <tr>
                <td style={cell}>
                  {t("kappa.cellHpJp")}: {fmtInt(m.humanPassJudgePass)}
                </td>
                <td style={cell}>
                  {t("kappa.cellHpJf")}: {fmtInt(m.humanPassJudgeFail)}
                </td>
              </tr>
              <tr>
                <td style={cell}>
                  {t("kappa.cellHfJp")}: {fmtInt(m.humanFailJudgePass)}
                </td>
                <td style={cell}>
                  {t("kappa.cellHfJf")}: {fmtInt(m.humanFailJudgeFail)}
                </td>
              </tr>
            </tbody>
          </table>
        </>
      ) : null}
    </Card>
  );
}

const cell = { border: "1px solid #2c313a", padding: "4px 8px" } as const;
