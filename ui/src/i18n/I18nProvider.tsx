/**
 * I18n Provider and translation hook.
 *
 * Provides a lightweight i18n system with:
 * - React context provider that wraps the app
 * - useTranslation hook for accessing translated strings
 * - Dot-notation key lookup (e.g., "cascade.statusRunning")
 * - Dynamic value interpolation (e.g., "Last updated {time}")
 * - Missing key fallback: returns the key itself as a debugging aid
 * - Development mode warnings for missing keys
 *
 * Adding a new locale requires only:
 * 1. Creating a new translation file (e.g., fi.ts) matching en.ts structure
 * 2. Registering it in the supported locales
 * 3. No component code changes needed
 */
import { createContext, useContext, useMemo, type ReactNode } from "react";
import en from "@/i18n/locales/en.ts";

// ── Types ─────────────────────────────────────────────────────────────

/** A flat record of translation strings, or nested records */
type TranslationValue = string | TranslationRecord;
type TranslationRecord = { readonly [key: string]: TranslationValue };

/** Supported locale codes */
export type Locale = "en";

/** Interpolation values for template strings */
type InterpolationValues = Record<string, string | number>;

/** The translation function returned by useTranslation */
export type TranslationFn = (key: string, values?: InterpolationValues) => string;

// ── Locale registry ───────────────────────────────────────────────────

const locales: Record<Locale, TranslationRecord> = {
  en,
};

const DEFAULT_LOCALE: Locale = "en";

// ── Core translation logic ────────────────────────────────────────────

/**
 * Resolve a dot-notation key against a translation record.
 *
 * Example: getNestedValue(translations, "cascade.statusRunning")
 * walks translations.cascade.statusRunning.
 *
 * Returns undefined if any segment is missing.
 */
function getNestedValue(
  obj: TranslationRecord,
  key: string,
): string | undefined {
  const segments = key.split(".");
  let current: TranslationValue = obj;

  for (const segment of segments) {
    if (typeof current !== "object" || current === null) {
      return undefined;
    }
    current = (current as TranslationRecord)[segment];
  }

  return typeof current === "string" ? current : undefined;
}

/**
 * Interpolate dynamic values into a translation string.
 *
 * Replaces {placeholder} tokens with corresponding values.
 * Example: interpolate("Last updated {time}", { time: "2 min ago" })
 *          → "Last updated 2 min ago"
 */
function interpolate(template: string, values?: InterpolationValues): string {
  if (!values) return template;

  return template.replace(/\{(\w+)\}/g, (match, key: string) => {
    const value = values[key];
    return value !== undefined ? String(value) : match;
  });
}

/**
 * Create a translation function for a given locale.
 */
function createTranslationFn(locale: Locale): TranslationFn {
  const translations = locales[locale] ?? locales[DEFAULT_LOCALE];

  return (key: string, values?: InterpolationValues): string => {
    const raw = getNestedValue(translations, key);

    if (raw === undefined) {
      if (import.meta.env.DEV) {
        console.warn(`[i18n] Missing translation key: "${key}" for locale "${locale}"`);
      }
      // Return the key itself as a fallback — visible debugging aid
      return values ? interpolate(key, values) : key;
    }

    return interpolate(raw, values);
  };
}

// ── React context ─────────────────────────────────────────────────────

interface I18nContextValue {
  /** Current locale code */
  locale: Locale;
  /** Translation function: t("key") or t("key", { name: "value" }) */
  t: TranslationFn;
}

const I18nContext = createContext<I18nContextValue | null>(null);

// ── Provider component ────────────────────────────────────────────────

interface I18nProviderProps {
  /** The active locale. Defaults to "en". */
  locale?: Locale;
  children: ReactNode;
}

/**
 * I18n provider component.
 *
 * Wraps the app and makes translations available to all descendants
 * via the useTranslation hook.
 *
 * Position in the provider hierarchy:
 *   ThemeProvider → I18nProvider → (AuthProvider) → GlobalStyles → BrowserRouter → Routes
 */
export function I18nProvider({ locale = DEFAULT_LOCALE, children }: I18nProviderProps) {
  const value = useMemo<I18nContextValue>(() => ({
    locale,
    t: createTranslationFn(locale),
  }), [locale]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

// ── Hook ──────────────────────────────────────────────────────────────

/**
 * Hook to access translations from any component.
 *
 * @returns {{ t: TranslationFn, locale: Locale }}
 *
 * Usage:
 *   const { t } = useTranslation();
 *   return <button>{t("common.save")}</button>;
 *
 * With interpolation:
 *   t("common.lastUpdated", { time: "2 min ago" })
 *   → "Last updated 2 min ago"
 */
export function useTranslation() {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useTranslation must be used within an I18nProvider");
  }
  return ctx;
}
