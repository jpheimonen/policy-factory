/**
 * Root application component.
 *
 * Provider hierarchy:
 *   ThemeProvider → I18nProvider → (future AuthProvider) → GlobalStyles → BrowserRouter → Routes
 *
 * Wraps the app in ThemeProvider with the resolved theme from the theme store,
 * then I18nProvider to make translations available to all descendants.
 */
import { ThemeProvider } from "styled-components";
import { GlobalStyles } from "@/styles/GlobalStyles.ts";
import { useThemeStore } from "@/stores/themeStore.ts";
import { I18nProvider, useTranslation } from "@/i18n/index.ts";
import { AppContainer } from "@/App.styles.ts";

/** Placeholder home content — uses translation keys, no hardcoded strings. */
function AppContent() {
  const { t } = useTranslation();

  return (
    <AppContainer>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "100vh",
        }}
      >
        <h1>{t("nav.appName")}</h1>
      </div>
    </AppContainer>
  );
}

export function App() {
  const resolvedTheme = useThemeStore((state) => state.resolvedTheme);

  return (
    <ThemeProvider theme={resolvedTheme}>
      <I18nProvider>
        <GlobalStyles />
        <AppContent />
      </I18nProvider>
    </ThemeProvider>
  );
}
