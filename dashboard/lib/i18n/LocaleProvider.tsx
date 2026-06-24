"use client";

import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";

import { dictionaries, en, type Locale, type TKey, translate } from "./dictionaries";

type Translate = (key: TKey, vars?: Record<string, string | number>) => string;

interface LocaleContextValue {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: Translate;
}

const STORAGE_KEY = "aegis.locale";

// Default context renders ENGLISH with no provider — so a stray render degrades to the
// canonical language instead of crashing. The real provider overrides it.
const LocaleContext = createContext<LocaleContextValue>({
  locale: "en",
  setLocale: () => {},
  t: (key, vars) => translate(en, en, key, vars),
});

function readStored(): Locale | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v === "en" || v === "es" ? v : null;
  } catch {
    return null; // SSR / privacy mode / disabled storage
  }
}

/**
 * Provides { locale, setLocale, t }. English is the canonical default; we NEVER
 * autodetect to Spanish. The stored preference is read AFTER mount (in an effect) so
 * the server render and the first client render both start at the `initialLocale`
 * (default "en") — no hydration mismatch. `initialLocale` also lets tests pin a locale.
 */
export function LocaleProvider({
  children,
  initialLocale,
}: {
  children: ReactNode;
  initialLocale?: Locale;
}) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale ?? "en");

  // Hydration-safe: pick up the persisted choice only after mount. Skipped when an
  // explicit initialLocale is given (tests / forced override).
  useEffect(() => {
    if (initialLocale) return;
    const stored = readStored();
    if (stored) setLocaleState(stored);
  }, [initialLocale]);

  // Keep <html lang> in sync for a11y / correct hyphenation.
  useEffect(() => {
    try {
      document.documentElement.lang = locale;
    } catch {
      // no document (SSR) — the static lang="en" in layout stands until hydration
    }
  }, [locale]);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // best-effort persistence; the toggle still works in-session
    }
  }, []);

  const t = useMemo<Translate>(
    () => (key, vars) => translate(dictionaries[locale], en, key, vars),
    [locale],
  );

  const value = useMemo<LocaleContextValue>(
    () => ({ locale, setLocale, t }),
    [locale, setLocale, t],
  );

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export function useLocale(): LocaleContextValue {
  return useContext(LocaleContext);
}
