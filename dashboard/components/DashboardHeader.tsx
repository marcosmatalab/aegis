"use client";

import { useLocale } from "@/lib/i18n/LocaleProvider";
import { LanguageToggle } from "./LanguageToggle";

/** Panel header: translated title + subtitle, with the language toggle at the top right.
 * `reportsDir` is data (rendered verbatim in <code>), passed from the server page.
 *
 * `isSnapshot` marks the GitHub Pages static export. A snapshot that looks like a
 * live view is exactly the kind of quiet dishonesty this dashboard exists to avoid,
 * so it says so on the page and gives the command that regenerates it. */
export function DashboardHeader({
  reportsDir,
  isSnapshot = false,
}: {
  reportsDir: string;
  isSnapshot?: boolean;
}) {
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
        {isSnapshot && (
          <p style={{ color: "#d29922", margin: "0.35rem 0 0", fontSize: 13 }}>
            {t("page.snapshotNotice")}
            <code>{t("page.snapshotCommand")}</code>
          </p>
        )}
      </div>
      <LanguageToggle />
    </header>
  );
}
