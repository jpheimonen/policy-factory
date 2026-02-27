/**
 * Root application component.
 *
 * Provider hierarchy (outermost → innermost):
 *   ThemeProvider → I18nProvider → GlobalStyles → BrowserRouter → Routes
 *
 * Route structure:
 *   /login — LoginPage (public)
 *   /register — RegisterPage (public, with redirect-if-users-exist guard)
 *   / — placeholder home page (protected)
 *   /layers/:slug — placeholder layer detail (protected)
 *   /layers/:slug/:item — placeholder item detail (protected)
 *   /ideas — placeholder ideas page (protected)
 *   /cascade — placeholder cascade viewer (protected)
 *   /activity — placeholder activity feed (protected)
 *   /history/:slug — placeholder version history (protected)
 *   /admin — placeholder admin panel (protected)
 *   * — catch-all redirects to /
 *
 * Auth initialization:
 *   On mount, the auth store initializes (restores JWT from localStorage).
 *   If no JWT is stored, the registration check runs to determine if the
 *   app should show login or registration.
 *   A brief loading state prevents flash of login page for already-authenticated users.
 */
import { useEffect } from "react";
import { ThemeProvider } from "styled-components";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { GlobalStyles } from "@/styles/GlobalStyles.ts";
import { useThemeStore } from "@/stores/themeStore.ts";
import { useAuthStore } from "@/stores/authStore.ts";
import { I18nProvider, useTranslation } from "@/i18n/index.ts";
import { AppContainer } from "@/App.styles.ts";
import { ProtectedRoute } from "@/components/organisms/ProtectedRoute.tsx";
import { AppLayout } from "@/components/organisms/AppLayout.tsx";
import { LoginPage } from "@/pages/auth/LoginPage.tsx";
import { RegisterPage } from "@/pages/auth/RegisterPage.tsx";
import { PlaceholderPage } from "@/pages/PlaceholderPage.tsx";

/** Loading spinner shown during auth initialization. */
function InitializingScreen() {
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
        <span>{t("common.initializing")}</span>
      </div>
    </AppContainer>
  );
}

/** Inner app content with routing — separated so it can use i18n and auth hooks. */
function AppContent() {
  const initialized = useAuthStore((s) => s.initialized);
  const initialize = useAuthStore((s) => s.initialize);

  useEffect(() => {
    initialize();
  }, [initialize]);

  // Show loading state while auth initializes (prevents flash of login page)
  if (!initialized) {
    return <InitializingScreen />;
  }

  return (
    <AppContainer>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />

          {/* Protected routes — wrapped in ProtectedRoute + AppLayout */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route
                index
                element={<PlaceholderPage titleKey="stackOverview.title" />}
              />
              <Route
                path="/layers/:slug"
                element={<PlaceholderPage titleKey="layers.narrativeSummary" />}
              />
              <Route
                path="/layers/:slug/:item"
                element={<PlaceholderPage titleKey="items.title" />}
              />
              <Route
                path="/ideas"
                element={<PlaceholderPage titleKey="nav.ideas" />}
              />
              <Route
                path="/cascade"
                element={<PlaceholderPage titleKey="nav.cascade" />}
              />
              <Route
                path="/activity"
                element={<PlaceholderPage titleKey="activity.title" />}
              />
              <Route
                path="/history/:slug"
                element={<PlaceholderPage titleKey="history.title" />}
              />
              <Route
                path="/admin"
                element={<PlaceholderPage titleKey="admin.title" />}
              />
            </Route>
          </Route>

          {/* Catch-all — redirect to home */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
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
