/**
 * Admin page — user management and system status.
 *
 * Route: /admin
 * Only accessible to admin users. Non-admins are redirected to home.
 *
 * Sections:
 *   1. User Management — list users, create new users, delete users
 *   2. System Status — heartbeat status + trigger, seed status
 *
 * All visible text uses i18n translation keys.
 */
import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "@/i18n/index.ts";
import { useAuthStore } from "@/stores/authStore.ts";
import { apiRequest, isApiError } from "@/lib/apiClient.ts";
import { Button, Badge, Input } from "@/components/atoms/index.ts";
import { LoadingState, ErrorState, FormField, ConfirmModal } from "@/components/molecules/index.ts";
import {
  PageWrapper,
  PageTitle,
  Section,
  SectionHeader,
  UserList,
  UserRow,
  UserEmail,
  YouIndicator,
  UserMeta,
  UserActions,
  CreateUserForm,
  FormFieldGroup,
  FormActions,
  FeedbackMessage,
  StatusGrid,
  StatusCard,
  StatusCardTitle,
  StatusItem,
  StatusDot,
  StatusActions,
} from "./AdminPage.styles.ts";

// ── Types ──────────────────────────────────────────────────────────────

interface UserRecord {
  id: string;
  email: string;
  role: string;
  created_at: string;
}

interface HeartbeatStatus {
  active: boolean;
  interval_seconds?: number;
  next_run?: string;
  currently_running?: boolean;
  latest_run?: {
    timestamp: string;
    highest_tier: number;
    outcome?: string;
  } | null;
}

interface SeedStatus {
  seeded: boolean;
}

// ── Helper: format date ────────────────────────────────────────────────

function formatDate(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return isoString;
  }
}

function formatDateTime(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoString;
  }
}

function formatInterval(seconds: number): string {
  if (seconds >= 3600) {
    const hours = Math.round(seconds / 3600);
    return `Every ${hours} hour${hours > 1 ? "s" : ""}`;
  }
  const minutes = Math.round(seconds / 60);
  return `Every ${minutes} minute${minutes > 1 ? "s" : ""}`;
}

// ── Component ──────────────────────────────────────────────────────────

export function AdminPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const currentUser = useAuthStore((s) => s.user);

  // ── Admin guard ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!isAdmin) {
      navigate("/", { replace: true });
    }
  }, [isAdmin, navigate]);

  // ── User management state ───────────────────────────────────────────
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [usersLoading, setUsersLoading] = useState(true);
  const [usersError, setUsersError] = useState<string | null>(null);

  // Create user form
  const [createEmail, setCreateEmail] = useState("");
  const [createPassword, setCreatePassword] = useState("");
  const [createLoading, setCreateLoading] = useState(false);
  const [createFeedback, setCreateFeedback] = useState<{
    type: "success" | "error";
    message: string;
  } | null>(null);

  // Delete confirmation
  const [deleteTarget, setDeleteTarget] = useState<UserRecord | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  // ── System status state ─────────────────────────────────────────────
  const [heartbeatStatus, setHeartbeatStatus] = useState<HeartbeatStatus | null>(null);
  const [seedStatus, setSeedStatus] = useState<SeedStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(true);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [triggerHeartbeatLoading, setTriggerHeartbeatLoading] = useState(false);

  // ── Data fetching ───────────────────────────────────────────────────

  const fetchUsers = useCallback(async () => {
    setUsersLoading(true);
    setUsersError(null);
    try {
      const data = await apiRequest<UserRecord[]>("/api/users/");
      setUsers(data);
    } catch (err) {
      const detail = isApiError(err) ? err.detail : t("errors.generic");
      setUsersError(detail);
    } finally {
      setUsersLoading(false);
    }
  }, [t]);

  const fetchStatus = useCallback(async () => {
    setStatusLoading(true);
    setStatusError(null);
    try {
      const [hb, seed] = await Promise.all([
        apiRequest<HeartbeatStatus>("/api/heartbeat/status").catch(() => null),
        apiRequest<SeedStatus>("/api/seed/status").catch(() => null),
      ]);
      setHeartbeatStatus(hb);
      setSeedStatus(seed);
    } catch (err) {
      const detail = isApiError(err) ? err.detail : t("errors.generic");
      setStatusError(detail);
    } finally {
      setStatusLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (isAdmin) {
      fetchUsers();
      fetchStatus();
    }
  }, [isAdmin, fetchUsers, fetchStatus]);

  // ── Validation ──────────────────────────────────────────────────────

  const emailValid = createEmail.includes("@");
  const passwordValid = createPassword.length >= 8;
  const formValid = emailValid && passwordValid;

  // ── Create user handler ─────────────────────────────────────────────

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formValid) return;

    setCreateLoading(true);
    setCreateFeedback(null);

    try {
      await apiRequest("/api/users/", {
        method: "POST",
        body: { email: createEmail, password: createPassword },
      });

      setCreateEmail("");
      setCreatePassword("");
      setCreateFeedback({
        type: "success",
        message: t("admin.createSuccess"),
      });

      // Auto-dismiss success after 3 seconds
      setTimeout(() => setCreateFeedback(null), 3000);

      // Refresh user list
      fetchUsers();
    } catch (err) {
      let message = t("admin.createError");
      if (isApiError(err)) {
        if (err.status === 409) {
          message = t("admin.emailAlreadyExists");
        } else {
          message = err.detail;
        }
      }
      setCreateFeedback({ type: "error", message });
    } finally {
      setCreateLoading(false);
    }
  };

  // ── Delete user handler ─────────────────────────────────────────────

  const handleDeleteConfirm = async () => {
    if (!deleteTarget) return;

    setDeleteLoading(true);
    try {
      await apiRequest(`/api/users/${deleteTarget.id}`, {
        method: "DELETE",
      });
      setDeleteTarget(null);
      fetchUsers();
    } catch (err) {
      const detail = isApiError(err) ? err.detail : t("admin.deleteError");
      setCreateFeedback({ type: "error", message: detail });
      setDeleteTarget(null);
    } finally {
      setDeleteLoading(false);
    }
  };

  // ── Trigger heartbeat handler ───────────────────────────────────────

  const handleTriggerHeartbeat = async () => {
    setTriggerHeartbeatLoading(true);
    try {
      await apiRequest("/api/heartbeat/trigger", { method: "POST" });
      // Refresh status after trigger
      setTimeout(fetchStatus, 1000);
    } catch (err) {
      if (isApiError(err) && err.status === 409) {
        // Already running — just refresh status
      }
    } finally {
      setTriggerHeartbeatLoading(false);
    }
  };

  // ── Guard: don't render for non-admins ──────────────────────────────
  if (!isAdmin) return null;

  // ── Email validation error message ──────────────────────────────────
  const emailError =
    createEmail.length > 0 && !emailValid
      ? t("admin.emailInvalid")
      : undefined;
  const passwordError =
    createPassword.length > 0 && !passwordValid
      ? t("admin.passwordTooShort")
      : undefined;

  return (
    <PageWrapper>
      <PageTitle>{t("admin.title")}</PageTitle>

      {/* ── User Management Section ──────────────────────────────────── */}
      <Section>
        <SectionHeader>{t("admin.userManagementHeading")}</SectionHeader>

        {/* Create user form */}
        <CreateUserForm onSubmit={handleCreateUser}>
          <FormFieldGroup>
            <FormField
              label={t("admin.emailLabel")}
              required
              htmlFor="create-email"
              error={emailError}
            >
              <Input
                id="create-email"
                type="email"
                value={createEmail}
                onChange={(e) => setCreateEmail(e.target.value)}
                placeholder={t("admin.emailPlaceholder")}
                $size="md"
                $error={!!emailError}
                autoComplete="off"
              />
            </FormField>
          </FormFieldGroup>
          <FormFieldGroup>
            <FormField
              label={t("admin.passwordLabel")}
              required
              htmlFor="create-password"
              error={passwordError}
            >
              <Input
                id="create-password"
                type="password"
                value={createPassword}
                onChange={(e) => setCreatePassword(e.target.value)}
                placeholder={t("admin.passwordPlaceholder")}
                $size="md"
                $error={!!passwordError}
                autoComplete="new-password"
              />
            </FormField>
          </FormFieldGroup>
          <FormActions>
            <Button
              type="submit"
              $variant="primary"
              $size="md"
              disabled={!formValid || createLoading}
              $loading={createLoading}
            >
              {createLoading ? t("admin.creating") : t("admin.createButton")}
            </Button>
          </FormActions>
        </CreateUserForm>

        {createFeedback && (
          <FeedbackMessage $variant={createFeedback.type}>
            {createFeedback.message}
          </FeedbackMessage>
        )}

        {/* User list */}
        {usersLoading ? (
          <LoadingState compact />
        ) : usersError ? (
          <ErrorState message={usersError} onRetry={fetchUsers} compact />
        ) : users.length === 0 ? (
          <UserMeta>{t("admin.noUsers")}</UserMeta>
        ) : (
          <UserList>
            {users.map((user) => {
              const isCurrentUser = user.id === currentUser?.id;
              return (
                <UserRow key={user.id} $isCurrentUser={isCurrentUser}>
                  <UserEmail>
                    {user.email}
                    {isCurrentUser && (
                      <YouIndicator>{t("admin.youIndicator")}</YouIndicator>
                    )}
                  </UserEmail>
                  <Badge
                    $variant={user.role === "admin" ? "info" : "neutral"}
                  >
                    {user.role === "admin"
                      ? t("admin.roleAdmin")
                      : t("admin.roleUser")}
                  </Badge>
                  <UserMeta>
                    {t("admin.createdAt", { time: formatDate(user.created_at) })}
                  </UserMeta>
                  <UserActions>
                    {!isCurrentUser && (
                      <Button
                        $variant="danger"
                        $size="sm"
                        onClick={() => setDeleteTarget(user)}
                      >
                        {t("admin.deleteButton")}
                      </Button>
                    )}
                  </UserActions>
                </UserRow>
              );
            })}
          </UserList>
        )}
      </Section>

      {/* ── System Status Section ────────────────────────────────────── */}
      <Section>
        <SectionHeader>
          {t("admin.systemStatusHeading")}
        </SectionHeader>

        {statusLoading ? (
          <LoadingState compact />
        ) : statusError ? (
          <ErrorState message={statusError} onRetry={fetchStatus} compact />
        ) : (
          <>
            <StatusGrid>
              {/* Heartbeat status card */}
              <StatusCard>
                <StatusCardTitle>
                  {t("admin.heartbeatStatusHeading")}
                </StatusCardTitle>
                {heartbeatStatus ? (
                  <>
                    <StatusItem>
                      <StatusDot $active={heartbeatStatus.active} />
                      {heartbeatStatus.active
                        ? t("admin.heartbeatActive")
                        : t("admin.heartbeatInactive")}
                    </StatusItem>
                    {heartbeatStatus.interval_seconds != null && (
                      <StatusItem>
                        {t("admin.heartbeatInterval", {
                          interval: formatInterval(heartbeatStatus.interval_seconds),
                        })}
                      </StatusItem>
                    )}
                    {heartbeatStatus.next_run && (
                      <StatusItem>
                        {t("admin.heartbeatNextRun", {
                          time: formatDateTime(heartbeatStatus.next_run),
                        })}
                      </StatusItem>
                    )}
                    {heartbeatStatus.latest_run ? (
                      <>
                        <StatusItem>
                          {t("admin.heartbeatLastRun", {
                            time: formatDateTime(heartbeatStatus.latest_run.timestamp),
                          })}
                        </StatusItem>
                        <StatusItem>
                          {t("admin.heartbeatLastTier", {
                            tier: String(heartbeatStatus.latest_run.highest_tier),
                          })}
                        </StatusItem>
                        {heartbeatStatus.latest_run.outcome && (
                          <StatusItem>
                            {t("admin.heartbeatLastOutcome", {
                              outcome: heartbeatStatus.latest_run.outcome,
                            })}
                          </StatusItem>
                        )}
                      </>
                    ) : (
                      <StatusItem>
                        {t("admin.heartbeatNoRuns")}
                      </StatusItem>
                    )}
                    <StatusActions>
                      <Button
                        $variant="secondary"
                        $size="sm"
                        onClick={handleTriggerHeartbeat}
                        disabled={
                          triggerHeartbeatLoading ||
                          heartbeatStatus.currently_running === true
                        }
                        $loading={triggerHeartbeatLoading}
                        title={
                          heartbeatStatus.currently_running
                            ? t("admin.heartbeatCurrentlyRunning")
                            : undefined
                        }
                      >
                        {triggerHeartbeatLoading
                          ? t("admin.triggerHeartbeatRunning")
                          : t("admin.triggerHeartbeatButton")}
                      </Button>
                    </StatusActions>
                  </>
                ) : (
                  <StatusItem>{t("admin.heartbeatInactive")}</StatusItem>
                )}
              </StatusCard>

              {/* Seed status card */}
              <StatusCard>
                <StatusCardTitle>
                  {t("admin.seedStatusHeading")}
                </StatusCardTitle>
                {seedStatus ? (
                  <>
                    <StatusItem>
                      <StatusDot $active={seedStatus.seeded} />
                      {seedStatus.seeded
                        ? t("admin.seedComplete")
                        : t("admin.seedNotComplete")}
                    </StatusItem>
                    {!seedStatus.seeded && (
                      <StatusItem>
                        {t("admin.seedGuidance")}
                      </StatusItem>
                    )}
                  </>
                ) : (
                  <StatusItem>{t("admin.seedNotComplete")}</StatusItem>
                )}
              </StatusCard>
            </StatusGrid>

            <StatusActions>
              <Button
                $variant="ghost"
                $size="sm"
                onClick={fetchStatus}
              >
                {t("admin.refreshButton")}
              </Button>
            </StatusActions>
          </>
        )}
      </Section>

      {/* ── Delete confirmation dialog ───────────────────────────────── */}
      <ConfirmModal
        isOpen={!!deleteTarget}
        onConfirm={handleDeleteConfirm}
        onCancel={() => setDeleteTarget(null)}
        title={t("admin.deleteConfirmTitle")}
        message={
          deleteTarget
            ? t("admin.deleteConfirm", { email: deleteTarget.email })
            : ""
        }
        confirmLabel={t("common.delete")}
        cancelLabel={t("common.cancel")}
        variant="danger"
        loading={deleteLoading}
      />
    </PageWrapper>
  );
}
