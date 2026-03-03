/**
 * Root application component.
 *
 * Provider hierarchy (outermost → innermost):
 *   ThemeProvider → I18nProvider → GlobalStyles → BrowserRouter → Routes
 *
 * Route structure:
 *   /login — LoginPage (public)
 *   /register — RegisterPage (public, with redirect-if-users-exist guard)
 *   / — StackOverviewPage (protected, home page)
 *   /layers/:slug — LayerDetailPage (protected)
 *   /layers/:slug/:item — ItemDetailPage (protected)
 *   /ideas — IdeasPage (protected)
 *   /cascade — CascadePage (protected)
 *   /activity — ActivityPage (protected)
 *   /history/:slug — HistoryPage (protected)
 *   /admin — AdminPage (protected)
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
import { StackOverviewPage } from "@/pages/StackOverviewPage.tsx";
import { LayerDetailPage } from "@/pages/LayerDetailPage.tsx";
import { ItemDetailPage } from "@/pages/ItemDetailPage.tsx";
import { IdeasPage } from "@/pages/IdeasPage.tsx";
import { CascadePage } from "@/pages/CascadePage.tsx";
import { ActivityPage } from "@/pages/ActivityPage.tsx";
import { HistoryPage } from "@/pages/HistoryPage.tsx";
import { AdminPage } from "@/pages/AdminPage.tsx";

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
              <Route index element={<StackOverviewPage />} />
              <Route path="/layers/:slug" element={<LayerDetailPage />} />
              <Route path="/layers/:slug/:item" element={<ItemDetailPage />} />
              <Route path="/ideas" element={<IdeasPage />} />
              <Route path="/cascade" element={<CascadePage />} />
              <Route path="/activity" element={<ActivityPage />} />
              <Route path="/history/:slug" element={<HistoryPage />} />
              <Route path="/admin" element={<AdminPage />} />
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
