/**
 * Navigation component.
 *
 * Horizontal header bar shown on all protected pages.
 * Features:
 * - App name / brand
 * - Nav links to main pages (home, ideas, cascade, activity)
 * - Admin link (only visible to admin users)
 * - Active route highlighting
 * - Cascade status indicator (idle / running / paused / failed)
 * - WebSocket connection status (reconnecting / connection lost)
 * - Current user email display
 * - Theme toggle (dark/light)
 * - Logout button
 *
 * All labels use i18n translation keys.
 */
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "@/i18n/index.ts";
import { useAuthStore } from "@/stores/authStore.ts";
import { useThemeStore, type ThemePreference } from "@/stores/themeStore.ts";
import { useCascadeStore } from "@/stores/cascadeStore.ts";
import { useWebSocketStatus } from "@/hooks/WebSocketProvider.tsx";
import { Button, IconButton } from "@/components/atoms/index.ts";
import {
  NavBar,
  NavBrand,
  NavLinks,
  NavLink,
  NavRight,
  UserEmail,
  NavDivider,
  CascadeStatusWrapper,
  CascadeStatusDot,
  CascadeStatusText,
  ConnectionStatusWrapper,
  ConnectionStatusText,
  type CascadeIndicatorStatus,
} from "./Navigation.styles.ts";

// ── SVG icons ────────────────────────────────────────────────────────

/** Simple SVG icons for theme toggle. Inline to avoid extra dependencies. */
function SunIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="5" />
      <line x1="12" y1="1" x2="12" y2="3" />
      <line x1="12" y1="21" x2="12" y2="23" />
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
      <line x1="1" y1="12" x2="3" y2="12" />
      <line x1="21" y1="12" x2="23" y2="12" />
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
    </svg>
  );
}

function MoonIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
    </svg>
  );
}

// ── Cascade status indicator ─────────────────────────────────────────

function CascadeStatusIndicator() {
  const { t } = useTranslation();
  const status = useCascadeStore((s) => s.status);
  const fetchStatus = useCascadeStore((s) => s.fetchStatus);

  // Fetch cascade status on mount
  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  // Map cascade store status to indicator status
  const indicatorStatus: CascadeIndicatorStatus =
    status === "running" || status === "queued"
      ? "running"
      : status === "paused"
        ? "paused"
        : status === "failed"
          ? "failed"
          : "idle";

  // Don't show the indicator when idle (clean UI)
  if (indicatorStatus === "idle") {
    return null;
  }

  const statusLabel =
    indicatorStatus === "running"
      ? t("nav.cascadeStatusRunning")
      : indicatorStatus === "paused"
        ? t("nav.cascadeStatusPaused")
        : indicatorStatus === "failed"
          ? t("nav.cascadeStatusFailed")
          : t("nav.cascadeStatusIdle");

  return (
    <CascadeStatusWrapper>
      <CascadeStatusDot $status={indicatorStatus} />
      <CascadeStatusText $status={indicatorStatus}>
        {statusLabel}
      </CascadeStatusText>
    </CascadeStatusWrapper>
  );
}

// ── Connection status indicator ──────────────────────────────────────

function ConnectionStatusIndicator() {
  const { t } = useTranslation();
  const wsStatus = useWebSocketStatus();

  // No WebSocket context (shouldn't happen inside protected routes)
  if (!wsStatus) return null;

  const { reconnecting, disconnected, reconnect } = wsStatus;

  if (reconnecting) {
    return (
      <ConnectionStatusWrapper>
        <CascadeStatusDot $status="paused" />
        <ConnectionStatusText>
          {t("nav.connectionReconnecting")}
        </ConnectionStatusText>
      </ConnectionStatusWrapper>
    );
  }

  if (disconnected) {
    return (
      <ConnectionStatusWrapper>
        <CascadeStatusDot $status="failed" />
        <ConnectionStatusText>
          {t("nav.connectionLost")}
        </ConnectionStatusText>
        <Button $variant="ghost" $size="sm" onClick={reconnect}>
          {t("nav.connectionReconnect")}
        </Button>
      </ConnectionStatusWrapper>
    );
  }

  // Connected — show nothing (default state)
  return null;
}

// ── Navigation component ─────────────────────────────────────────────

export function Navigation() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const logout = useAuthStore((s) => s.logout);
  const preference = useThemeStore((s) => s.preference);
  const setPreference = useThemeStore((s) => s.setPreference);

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const handleThemeToggle = () => {
    const nextPreference: ThemePreference =
      preference === "dark"
        ? "light"
        : preference === "light"
          ? "system"
          : "dark";
    setPreference(nextPreference);
  };

  /** Whether the current resolved theme is dark (for icon display). */
  const isDarkResolved = useThemeStore(
    (s) => s.resolvedTheme.colors.bg.primary === "#0a0a0c",
  );

  return (
    <NavBar>
      <NavBrand>{t("nav.appName")}</NavBrand>

      <NavLinks>
        <NavLink to="/" end>
          {t("nav.home")}
        </NavLink>
        <NavLink to="/ideas">{t("nav.ideas")}</NavLink>
        <NavLink to="/cascade">{t("nav.cascade")}</NavLink>
        <NavLink to="/activity">{t("nav.activity")}</NavLink>
        {isAdmin && <NavLink to="/admin">{t("nav.admin")}</NavLink>}
      </NavLinks>

      <CascadeStatusIndicator />
      <ConnectionStatusIndicator />

      <NavRight>
        {user && <UserEmail>{user.email}</UserEmail>}

        <NavDivider />

        <IconButton
          $variant="ghost"
          $size="sm"
          onClick={handleThemeToggle}
          title={
            preference === "dark"
              ? "Switch to light mode"
              : preference === "light"
                ? "Switch to system mode"
                : "Switch to dark mode"
          }
        >
          {isDarkResolved ? <SunIcon /> : <MoonIcon />}
        </IconButton>

        <Button $variant="ghost" $size="sm" onClick={handleLogout}>
          {t("nav.logout")}
        </Button>
      </NavRight>
    </NavBar>
  );
}
