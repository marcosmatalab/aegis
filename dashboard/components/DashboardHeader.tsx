"use client";

import { useLocale } from "@/lib/i18n/LocaleProvider";
import { LanguageToggle } from "./LanguageToggle";

/** Panel header: translated title + subtitle, with the language toggle at the top right.
 * `reportsDir` is data (rendered verbatim in <code>), passed from the server page. */
export function DashboardHeader({ reportsDir }: { reportsDir: string }) {
  const { t } = useLocale();
  return (
    <header
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        gap: "1rem",
      }}
    >
      <div>
        <h1 style={{ margin: 0 }}>{t("page.title")}</h1>
        <p style={{ color: "#9aa0aa", margin: "0.35rem 0 0", fontSize: 13 }}>
          {t("page.subtitlePre")}
          <code>{reportsDir}</code>
          {t("page.subtitlePost")}
        </p>
      </div>
      <LanguageToggle />
    </header>
  );
}
