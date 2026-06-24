"use client";

import type { TKey } from "@/lib/i18n/dictionaries";
import { useLocale } from "@/lib/i18n/LocaleProvider";

/**
 * Explicit "this report/datum is absent" panel. Used whenever a report is missing or
 * unparseable — so a gap reads as an honest "Not available" (with the command to
 * produce it), NEVER as a zero, a blank, or an empty chart that looks fine.
 *
 * Takes i18n KEYS (not literal text) so a server page can choose the strings without
 * translating; `command` is the literal CLI command, rendered verbatim (never translated).
 */
export function AbsentPanel({
  titleKey,
  reasonKey,
  command,
}: {
  titleKey: TKey;
  reasonKey: TKey;
  command?: string;
}) {
  const { t } = useLocale();
  return (
    <section
      data-absent="true"
      style={{
        border: "1px dashed #39404a",
        borderRadius: 8,
        padding: "1rem",
        color: "#9aa0aa",
        background: "#14171d",
      }}
    >
      <h3 style={{ margin: "0 0 0.25rem" }}>{t(titleKey)}</h3>
      <p style={{ margin: 0 }}>
        <strong>{t("absent.notAvailable")}</strong> — {t(reasonKey)}
      </p>
      {command ? (
        <p style={{ margin: "0.35rem 0 0", fontSize: 13, opacity: 0.85 }}>
          {t("absent.runToProduce")} <code>{command}</code>
        </p>
      ) : null}
    </section>
  );
}
