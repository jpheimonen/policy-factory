/**
 * i18n testing utilities.
 *
 * Provides helpers for rendering components that use the useTranslation hook
 * in tests, without needing the full app provider stack.
 *
 * Two modes:
 * 1. Passthrough mode (default): t("some.key") returns "some.key"
 *    — useful for assertions on translation keys.
 * 2. Real translations mode: t("some.key") returns the English string
 *    — useful for assertions on user-visible text.
 *
 * Usage:
 *   import { renderWithI18n, renderWithI18nReal } from '@/i18n/test-utils';
 *
 *   // Passthrough — assert on keys
 *   const { getByText } = renderWithI18n(<MyComponent />);
 *   expect(getByText("common.save")).toBeInTheDocument();
 *
 *   // Real translations — assert on English text
 *   const { getByText } = renderWithI18nReal(<MyComponent />);
 *   expect(getByText("Save")).toBeInTheDocument();
 */
import { render, type RenderOptions } from "@testing-library/react";
import type { ReactNode, ReactElement } from "react";
import { I18nProvider } from "@/i18n/I18nProvider.tsx";
import { ThemeProvider } from "styled-components";
import { darkTheme } from "@/styles/theme.ts";

// ── Wrapper with real English translations ────────────────────────────

/**
 * Wrapper that provides both ThemeProvider and I18nProvider with real
 * English translations. Suitable for component tests that need both
 * theme tokens and translation strings.
 */
function AllProviders({ children }: { children: ReactNode }) {
  return (
    <ThemeProvider theme={darkTheme}>
      <I18nProvider locale="en">{children}</I18nProvider>
    </ThemeProvider>
  );
}

/**
 * Render a component wrapped in ThemeProvider + I18nProvider with
 * real English translations.
 *
 * Assertions can match on the actual English strings:
 *   expect(getByText("Save")).toBeInTheDocument();
 */
export function renderWithI18n(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">,
) {
  return render(ui, { wrapper: AllProviders, ...options });
}

// ── Standalone I18nProvider wrapper (no theme) ────────────────────────

/**
 * Minimal wrapper with only the I18nProvider.
 * Use when testing i18n behavior in isolation.
 */
function I18nOnly({ children }: { children: ReactNode }) {
  return <I18nProvider locale="en">{children}</I18nProvider>;
}

/**
 * Render with only the I18nProvider (no ThemeProvider).
 * Useful for testing hooks or non-styled components.
 */
export function renderWithI18nOnly(
  ui: ReactElement,
  options?: Omit<RenderOptions, "wrapper">,
) {
  return render(ui, { wrapper: I18nOnly, ...options });
}
