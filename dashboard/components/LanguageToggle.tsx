"use client";

import type { Locale } from "@/lib/i18n/dictionaries";
import { useLocale } from "@/lib/i18n/LocaleProvider";

const LOCALES: Locale[] = ["en", "es"];

/** EN/ES language switch. Real buttons with aria-pressed; the active one is highlighted. */
export function LanguageToggle() {
  const { locale, setLocale, t } = useLocale();
  return (
    // biome-ignore lint/a11y/useSemanticElements: a labelled button group is the intended toggle; a <fieldset> would add unwanted chrome
    <div
      role="group"
      aria-label={t("toggle.aria")}
      style={{
        display: "inline-flex",
        border: "1px solid #2c313a",
        borderRadius: 999,
        overflow: "hidden",
      }}
    >
      {LOCALES.map((l) => {
        const active = locale === l;
        return (
          <button
            key={l}
            type="button"
            aria-pressed={active}
            onClick={() => setLocale(l)}
            style={{
              padding: "3px 12px",
              fontSize: 12,
              fontWeight: 600,
              cursor: "pointer",
              border: "none",
              background: active ? "#1f5c39" : "transparent",
              color: active ? "#5ee08a" : "#9aa0aa",
            }}
          >
            {l.toUpperCase()}
          </button>
        );
      })}
    </div>
  );
}
