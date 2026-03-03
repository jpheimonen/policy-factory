/**
 * Live Cascade Viewer page.
 *
 * Route: /cascade
 *
 * Displays the real-time cascade state:
 * - Running: progress indicator, active agent label, streaming text panel
 * - Paused: error details with resume/cancel controls
 * - Idle: most recently completed cascade summary + history list
 *
 * All real-time data comes from the cascade store (updated via WebSocket).
 * Initial state and history data are fetched from REST endpoints on mount.
 *
 * The page does not manage its own WebSocket connection — it reads from
 * the cascade store which is kept current by the central event dispatcher.
 */
import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { useTranslation } from "@/i18n/index.ts";
import { useCascadeStore } from "@/stores/cascadeStore.ts";
import type { CascadeStep } from "@/stores/cascadeStore.ts";
import { LAYER_NAME_KEYS } from "@/lib/layerConstants.ts";
import { apiRequest } from "@/lib/apiClient.ts";
import { formatRelativeTime } from "@/lib/timeUtils.ts";
import { Badge, Button, Text } from "@/components/atoms/index.ts";
import { EmptyState } from "@/components/molecules/index.ts";
import { useAutoScroll } from "@/hooks/useAutoScroll.ts";
import type { BadgeVariant } from "@/components/atoms/index.ts";
import {
  PageWrapper,
  PageHeader,
  HeaderLeft,
  HeaderRight,
  HeaderMeta,
  ProgressContainer,
  CompactProgress,
  CompactProgressText,
  CompactProgressBar,
  CompactProgressFill,
  DesktopProgress,
  ProgressLayerGroup,
  ProgressLayerName,
  ProgressSteps,
  ProgressStepDot,
  ProgressStepLabel,
  ProgressArrow,
  AgentLabel,
  AgentSpinner,
  StreamingContainer,
  StreamingScroller,
  StreamingText,
  StreamingCursor,
  StreamingEmpty,
  StreamingEmptySpinner,
  ErrorCard,
  ErrorTitle,
  ErrorDetail,
  ErrorActions,
  QueueSection,
  QueueEntry,
  QueueEntryInfo,
  QueueEntryTitle,
  QueueEntryMeta,
  HistorySection,
  SectionHeading,
  HistoryEntry,
  HistoryEntryHeader,
  HistoryEntryLeft,
  HistoryEntryRight,
  HistoryEntryMeta,
  HistoryDetail,
  IdleContainer,
  LayerBadge,
} from "./CascadePage.styles.ts";

// ── Constants ────────────────────────────────────────────────────────

/** Canonical layer order (bottom to top) */
const LAYER_ORDER: readonly string[] = [
  "values",
  "situational-awareness",
  "strategic-objectives",
  "tactical-objectives",
  "policies",
];

/** Steps in order for progress tracking */
const STEP_ORDER: CascadeStep[] = ["generation", "critics", "synthesis"];

/** Step i18n keys */
const STEP_KEYS: Record<CascadeStep, string> = {
  generation: "cascade.stepGeneration",
  critics: "cascade.stepCritics",
  synthesis: "cascade.stepSynthesis",
};

// ── API types ────────────────────────────────────────────────────────

interface CascadeStatusFull {
  status: string;
  cascade_id: string | null;
  current_layer: string | null;
  current_step: string | null;
  starting_layer: string | null;
  trigger_source: string | null;
  started_at: string | null;
  error_message: string | null;
  queue_depth: number;
  queue_entries: QueueEntryData[];
  last_completed_id: string | null;
}

interface QueueEntryData {
  id: string;
  trigger_source: string;
  starting_layer: string;
  queued_at: string;
}

interface CascadeHistoryItem {
  id: string;
  trigger_source: string;
  starting_layer: string;
  status: string;
  created_at: string;
  completed_at: string | null;
}

interface CascadeDetail {
  id: string;
  trigger_source: string;
  starting_layer: string;
  current_layer: string;
  current_step: string;
  status: string;
  error_message: string | null;
  error_layer: string | null;
  context: string | null;
  created_at: string;
  completed_at: string | null;
  agent_runs: AgentRunInfo[];
}

interface AgentRunInfo {
  id: string;
  agent_type: string;
  agent_label: string;
  model: string;
  target_layer: string;
  started_at: string;
  completed_at: string | null;
  success: boolean;
  error_message: string | null;
  cost_usd: number;
}

// ── Utility functions ────────────────────────────────────────────────

function getLayersInCascade(startingLayer: string): string[] {
  const startIdx = LAYER_ORDER.indexOf(startingLayer);
  if (startIdx === -1) return [...LAYER_ORDER];
  return LAYER_ORDER.slice(startIdx) as string[];
}

function formatDuration(start: string, end: string): string {
  const diffMs = new Date(end).getTime() - new Date(start).getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return `${diffSec}s`;
  const min = Math.floor(diffSec / 60);
  const sec = diffSec % 60;
  return `${min}m ${sec}s`;
}

function getTriggerSourceLabel(source: string, t: (key: string) => string): string {
  switch (source) {
    case "user_input":
      return t("cascade.triggerUserInput");
    case "layer_refresh":
      return t("cascade.triggerLayerRefresh");
    case "heartbeat":
      return t("cascade.triggerHeartbeat");
    case "seed":
      return t("cascade.triggerSeed");
    default:
      return t("cascade.triggerUnknown");
  }
}

function getStatusBadgeVariant(status: string): BadgeVariant {
  switch (status) {
    case "running":
      return "info";
    case "paused":
      return "warning";
    case "failed":
      return "error";
    case "completed":
      return "success";
    case "cancelled":
    case "queued":
    case "idle":
    default:
      return "neutral";
  }
}

function getStatusTranslationKey(status: string): string {
  switch (status) {
    case "idle":
      return "cascade.statusIdle";
    case "running":
      return "cascade.statusRunning";
    case "paused":
      return "cascade.statusPaused";
    case "completed":
      return "cascade.statusCompleted";
    case "failed":
      return "cascade.statusFailed";
    case "cancelled":
      return "cascade.statusCancelled";
    case "queued":
      return "cascade.statusQueued";
    default:
      return "cascade.statusIdle";
  }
}

// ── Component ────────────────────────────────────────────────────────

export function CascadePage() {
  const { t } = useTranslation();

  // Cascade store state (real-time via WebSocket)
  const status = useCascadeStore((s) => s.status);
  const cascadeId = useCascadeStore((s) => s.cascadeId);
  const currentLayer = useCascadeStore((s) => s.currentLayer);
  const currentStep = useCascadeStore((s) => s.currentStep);
  const queueDepth = useCascadeStore((s) => s.queueDepth);
  const errorInfo = useCascadeStore((s) => s.errorInfo);
  const currentAgentLabel = useCascadeStore((s) => s.currentAgentLabel);
  const streamingText = useCascadeStore((s) => s.streamingText);
  const fetchStatus = useCascadeStore((s) => s.fetchStatus);

  // Local state for REST-loaded data
  const [statusData, setStatusData] = useState<CascadeStatusFull | null>(null);
  const [historyItems, setHistoryItems] = useState<CascadeHistoryItem[]>([]);
  const [expandedHistoryId, setExpandedHistoryId] = useState<string | null>(null);
  const [historyDetails, setHistoryDetails] = useState<Record<string, CascadeDetail>>({});

  // Control button loading states
  const [pauseLoading, setPauseLoading] = useState(false);
  const [resumeLoading, setResumeLoading] = useState(false);
  const [cancelLoading, setCancelLoading] = useState(false);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [removingQueueId, setRemovingQueueId] = useState<string | null>(null);

  // Track previous status for detecting transitions
  const prevStatusRef = useRef(status);

  // Auto-scroll for streaming text
  const { ref: scrollerRef } = useAutoScroll<HTMLDivElement>(streamingText.length);

  // ── Data fetching ────────────────────────────────────────────────

  const fetchFullStatus = useCallback(async () => {
    try {
      const data = await apiRequest<CascadeStatusFull>("/api/cascade/status");
      setStatusData(data);
    } catch {
      // Cascade endpoint may not exist yet
    }
  }, []);

  const fetchHistory = useCallback(async () => {
    try {
      const data = await apiRequest<CascadeHistoryItem[]>("/api/cascade/history");
      setHistoryItems(data);
    } catch {
      // History endpoint may not exist yet
    }
  }, []);

  const fetchCascadeDetail = useCallback(async (id: string) => {
    try {
      const data = await apiRequest<CascadeDetail>(`/api/cascade/${id}`);
      setHistoryDetails((prev) => ({ ...prev, [id]: data }));
    } catch {
      // Detail fetch failed — silently ignore
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchStatus();
    fetchFullStatus();
  }, [fetchStatus, fetchFullStatus]);

  // Fetch history when idle
  useEffect(() => {
    if (status === "idle") {
      fetchHistory();
    }
  }, [status, fetchHistory]);

  // Re-fetch when cascade completes (status transitions from running to idle)
  useEffect(() => {
    if (prevStatusRef.current === "running" && status === "idle") {
      fetchHistory();
      fetchFullStatus();
    }
    prevStatusRef.current = status;
  }, [status, fetchHistory, fetchFullStatus]);

  // ── Control actions ──────────────────────────────────────────────

  const handlePause = useCallback(async () => {
    if (!cascadeId) return;
    setPauseLoading(true);
    try {
      await apiRequest(`/api/cascade/${cascadeId}/pause`, { method: "POST" });
    } catch {
      // Error handled by store via WebSocket event
    } finally {
      setPauseLoading(false);
    }
  }, [cascadeId]);

  const handleResume = useCallback(async () => {
    if (!cascadeId) return;
    setResumeLoading(true);
    try {
      await apiRequest(`/api/cascade/${cascadeId}/resume`, { method: "POST" });
    } catch {
      // Error handled by store via WebSocket event
    } finally {
      setResumeLoading(false);
    }
  }, [cascadeId]);

  const handleCancel = useCallback(async () => {
    if (!cascadeId) return;
    if (!confirmingCancel) {
      setConfirmingCancel(true);
      return;
    }
    setCancelLoading(true);
    try {
      await apiRequest(`/api/cascade/${cascadeId}/cancel`, { method: "POST" });
    } catch {
      // Error handled by store via WebSocket event
    } finally {
      setCancelLoading(false);
      setConfirmingCancel(false);
    }
  }, [cascadeId, confirmingCancel]);

  // Reset cancel confirmation when status changes
  useEffect(() => {
    setConfirmingCancel(false);
  }, [status]);

  const handleRemoveFromQueue = useCallback(async (queueId: string) => {
    setRemovingQueueId(queueId);
    try {
      await apiRequest(`/api/cascade/queue/${queueId}`, { method: "DELETE" });
      // Remove from local state
      setStatusData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          queue_entries: prev.queue_entries.filter((e) => e.id !== queueId),
          queue_depth: Math.max(0, prev.queue_depth - 1),
        };
      });
    } catch {
      // Queue removal failed
    } finally {
      setRemovingQueueId(null);
    }
  }, []);

  const handleHistoryClick = useCallback(
    (id: string) => {
      setExpandedHistoryId((prev) => {
        const newId = prev === id ? null : id;
        if (newId && !historyDetails[newId]) {
          fetchCascadeDetail(newId);
        }
        return newId;
      });
    },
    [fetchCascadeDetail, historyDetails],
  );

  // ── Derived data ─────────────────────────────────────────────────

  const cascadeLayers = useMemo(() => {
    const sl =
      statusData?.starting_layer ??
      statusData?.current_layer ??
      currentLayer ??
      "values";
    return getLayersInCascade(sl);
  }, [statusData, currentLayer]);

  const queueEntries = statusData?.queue_entries ?? [];

  // ── Rendering ────────────────────────────────────────────────────

  const isRunning = status === "running";
  const isPaused = status === "paused" || status === "failed";
  const isIdle = status === "idle";

  return (
    <PageWrapper>
      {/* ── Page Header ──────────────────────────────────────── */}
      <PageHeader>
        <HeaderLeft>
          <Text as="h1" $variant="heading" $size="xl">
            {t("cascade.title")}
          </Text>
          <Badge $variant={getStatusBadgeVariant(status)}>
            {t(getStatusTranslationKey(status))}
          </Badge>
        </HeaderLeft>
        <HeaderRight>
          {(isRunning || isPaused) && statusData?.trigger_source && (
            <HeaderMeta>
              <span>
                {t("cascade.triggerSource", {
                  source: getTriggerSourceLabel(statusData.trigger_source, t),
                })}
              </span>
              {statusData.started_at && (
                <span>
                  {t("cascade.startedAt", {
                    time: formatRelativeTime(statusData.started_at),
                  })}
                </span>
              )}
            </HeaderMeta>
          )}
          {isRunning && (
            <Button
              $variant="outline"
              $size="sm"
              $loading={pauseLoading}
              onClick={handlePause}
            >
              {pauseLoading
                ? t("cascade.pausing")
                : t("cascade.pauseButton")}
            </Button>
          )}
        </HeaderRight>
      </PageHeader>

      {/* ── Running state ────────────────────────────────────── */}
      {isRunning && (
        <>
          <CascadeProgressIndicator
            layers={cascadeLayers}
            currentLayer={currentLayer}
            currentStep={currentStep}
            cascadeStatus="running"
            t={t}
          />
          <ActiveAgentDisplay
            agentLabel={currentAgentLabel}
            currentLayer={currentLayer}
            currentStep={currentStep}
            t={t}
          />
          <StreamingTextPanel
            text={streamingText}
            isStreaming={isRunning}
            scrollerRef={scrollerRef}
            t={t}
          />
        </>
      )}

      {/* ── Paused/Failed state ──────────────────────────────── */}
      {isPaused && (
        <>
          <CascadeProgressIndicator
            layers={cascadeLayers}
            currentLayer={currentLayer}
            currentStep={currentStep}
            cascadeStatus="failed"
            t={t}
          />
          <ErrorCard>
            <ErrorTitle>{t("cascade.errorDisplay")}</ErrorTitle>
            {currentLayer && (
              <ErrorDetail>
                {t("cascade.errorAtLayer", {
                  layer: t(LAYER_NAME_KEYS[currentLayer] ?? currentLayer),
                })}
                {currentStep && (
                  <>
                    {" \u2014 "}
                    {t("cascade.errorAtStep", {
                      step: t(STEP_KEYS[currentStep] ?? currentStep),
                    })}
                  </>
                )}
              </ErrorDetail>
            )}
            {errorInfo && (
              <ErrorDetail>
                {t("cascade.errorMessage", { message: errorInfo })}
              </ErrorDetail>
            )}
            <ErrorActions>
              <Button
                $variant="primary"
                $size="md"
                $loading={resumeLoading}
                onClick={handleResume}
              >
                {resumeLoading
                  ? t("cascade.resuming")
                  : t("cascade.resumeButton")}
              </Button>
              <Button
                $variant={confirmingCancel ? "danger" : "outline"}
                $size="md"
                $loading={cancelLoading}
                onClick={handleCancel}
              >
                {cancelLoading
                  ? t("cascade.cancelling")
                  : confirmingCancel
                    ? t("cascade.confirmCancel")
                    : t("cascade.cancelButton")}
              </Button>
            </ErrorActions>
          </ErrorCard>
          {/* Show last streaming text if available */}
          {streamingText && (
            <StreamingTextPanel
              text={streamingText}
              isStreaming={false}
              scrollerRef={scrollerRef}
              t={t}
            />
          )}
        </>
      )}

      {/* ── Idle state ───────────────────────────────────────── */}
      {isIdle && (
        <CascadeIdleView
          historyItems={historyItems}
          expandedHistoryId={expandedHistoryId}
          historyDetails={historyDetails}
          onHistoryClick={handleHistoryClick}
          t={t}
        />
      )}

      {/* ── Queue section ────────────────────────────────────── */}
      {(queueDepth > 0 || queueEntries.length > 0) && (
        <CascadeQueueSection
          entries={queueEntries}
          removingId={removingQueueId}
          onRemove={handleRemoveFromQueue}
          t={t}
        />
      )}
    </PageWrapper>
  );
}

// ── Sub-components ─────────────────────────────────────────────────

/** Progress indicator showing cascade journey through layers */
function CascadeProgressIndicator({
  layers,
  currentLayer,
  currentStep,
  cascadeStatus,
  t,
}: {
  layers: string[];
  currentLayer: string | null;
  currentStep: CascadeStep | null;
  cascadeStatus: "running" | "failed";
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const currentLayerIdx = currentLayer ? layers.indexOf(currentLayer) : -1;

  function getLayerState(
    idx: number,
  ): "completed" | "active" | "upcoming" | "failed" {
    if (idx < currentLayerIdx) return "completed";
    if (idx === currentLayerIdx) {
      return cascadeStatus === "failed" ? "failed" : "active";
    }
    return "upcoming";
  }

  function getStepState(
    layerIdx: number,
    stepIdx: number,
  ): "done" | "active" | "pending" | "failed" {
    const layerState = getLayerState(layerIdx);
    if (layerState === "completed") return "done";
    if (layerState === "upcoming") return "pending";

    const currentStepIdx = currentStep ? STEP_ORDER.indexOf(currentStep) : -1;
    if (layerState === "failed") {
      if (stepIdx < currentStepIdx) return "done";
      if (stepIdx === currentStepIdx) return "failed";
      return "pending";
    }
    // active
    if (stepIdx < currentStepIdx) return "done";
    if (stepIdx === currentStepIdx) return "active";
    return "pending";
  }

  // Calculate progress percentage for compact view
  const totalSteps = layers.length * 3;
  let completedSteps = 0;
  for (let li = 0; li < layers.length; li++) {
    for (let si = 0; si < 3; si++) {
      const state = getStepState(li, si);
      if (state === "done") completedSteps++;
      if (state === "active") completedSteps += 0.5;
    }
  }
  const progressPercent =
    totalSteps > 0 ? (completedSteps / totalSteps) * 100 : 0;

  const layerName = currentLayer
    ? t(LAYER_NAME_KEYS[currentLayer] ?? currentLayer)
    : "";
  const stepName = currentStep ? t(STEP_KEYS[currentStep]) : "";
  const layerNum = currentLayerIdx + 1;

  return (
    <ProgressContainer>
      {/* Compact view for mobile */}
      <CompactProgress>
        <CompactProgressText>
          {currentLayer
            ? `${t("cascade.progress", { current: String(layerNum), total: String(layers.length) })}: ${layerName} \u2014 ${stepName}`
            : t("cascade.statusRunning")}
        </CompactProgressText>
        <CompactProgressBar>
          <CompactProgressFill
            $percent={progressPercent}
            $color="currentColor"
          />
        </CompactProgressBar>
      </CompactProgress>

      {/* Desktop step sequence */}
      <DesktopProgress>
        {layers.map((slug, idx) => {
          const layerState = getLayerState(idx);
          return (
            <ProgressLayerItem
              key={slug}
              slug={slug}
              layerState={layerState}
              stepStates={STEP_ORDER.map((_, si) => getStepState(idx, si))}
              isLast={idx === layers.length - 1}
              t={t}
            />
          );
        })}
      </DesktopProgress>
    </ProgressContainer>
  );
}

/** Individual layer in the progress indicator */
function ProgressLayerItem({
  slug,
  layerState,
  stepStates,
  isLast,
  t,
}: {
  slug: string;
  layerState: "completed" | "active" | "upcoming" | "failed";
  stepStates: ("done" | "active" | "pending" | "failed")[];
  isLast: boolean;
  t: (key: string) => string;
}) {
  // Find which step label to show (the active or failed one)
  const activeStepLabel = STEP_ORDER.reduce<string | null>((acc, step, si) => {
    if (stepStates[si] === "active" || stepStates[si] === "failed") {
      return t(STEP_KEYS[step]);
    }
    return acc;
  }, null);

  return (
    <>
      <ProgressLayerGroup $state={layerState} $layerSlug={slug}>
        <ProgressLayerName $layerSlug={slug}>
          {t(LAYER_NAME_KEYS[slug] ?? slug)}
        </ProgressLayerName>
        <ProgressSteps>
          {STEP_ORDER.map((step, si) => (
            <span key={step} title={t(STEP_KEYS[step])}>
              <ProgressStepDot
                $state={stepStates[si]}
                $layerSlug={slug}
              />
            </span>
          ))}
        </ProgressSteps>
        {activeStepLabel && (
          <ProgressStepLabel>{activeStepLabel}</ProgressStepLabel>
        )}
      </ProgressLayerGroup>
      {!isLast && <ProgressArrow>&rarr;</ProgressArrow>}
    </>
  );
}

/** Active agent label display */
function ActiveAgentDisplay({
  agentLabel,
  currentLayer,
  currentStep,
  t,
}: {
  agentLabel: string | null;
  currentLayer: string | null;
  currentStep: CascadeStep | null;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  const displayText = agentLabel
    ? t("cascade.currentAgent", { agent: agentLabel })
    : currentStep && currentLayer
      ? (() => {
          const layerName = t(
            LAYER_NAME_KEYS[currentLayer] ?? currentLayer,
          );
          switch (currentStep) {
            case "generation":
              return t("cascade.generatingLayer", { layer: layerName });
            case "critics":
              return t("cascade.runningCritics", { layer: layerName });
            case "synthesis":
              return t("cascade.synthesizingLayer", { layer: layerName });
            default:
              return t("cascade.processingLayer", { layer: layerName });
          }
        })()
      : t("cascade.statusRunning");

  return (
    <AgentLabel $layerSlug={currentLayer ?? undefined}>
      <AgentSpinner />
      {displayText}
    </AgentLabel>
  );
}

/** Streaming text panel */
function StreamingTextPanel({
  text,
  isStreaming,
  scrollerRef,
  t,
}: {
  text: string;
  isStreaming: boolean;
  scrollerRef: React.RefObject<HTMLDivElement | null>;
  t: (key: string) => string;
}) {
  return (
    <StreamingContainer>
      <StreamingScroller ref={scrollerRef}>
        {text ? (
          <StreamingText>
            {text}
            {isStreaming && <StreamingCursor />}
          </StreamingText>
        ) : isStreaming ? (
          <StreamingEmpty>
            <StreamingEmptySpinner />
            {t("cascade.waitingForOutput")}
          </StreamingEmpty>
        ) : (
          <StreamingEmpty>{t("cascade.streamingPaused")}</StreamingEmpty>
        )}
      </StreamingScroller>
    </StreamingContainer>
  );
}

/** Idle state view with last cascade summary and history */
function CascadeIdleView({
  historyItems,
  expandedHistoryId,
  historyDetails,
  onHistoryClick,
  t,
}: {
  historyItems: CascadeHistoryItem[];
  expandedHistoryId: string | null;
  historyDetails: Record<string, CascadeDetail>;
  onHistoryClick: (id: string) => void;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  if (historyItems.length === 0) {
    return (
      <IdleContainer>
        <EmptyState
          title={t("cascade.noCascadeHistory")}
          subtitle={t("cascade.idleDescription")}
        />
      </IdleContainer>
    );
  }

  // Most recent cascade as summary
  const lastCascade = historyItems[0];

  return (
    <HistorySection>
      {/* Last cascade summary */}
      {lastCascade && (
        <>
          <SectionHeading>{t("cascade.lastCascadeSummary")}</SectionHeading>
          <HistoryEntry onClick={() => onHistoryClick(lastCascade.id)}>
            <HistoryEntryHeader>
              <HistoryEntryLeft>
                <LayerBadge $layerSlug={lastCascade.starting_layer}>
                  {t(
                    LAYER_NAME_KEYS[lastCascade.starting_layer] ??
                      lastCascade.starting_layer,
                  )}
                </LayerBadge>
                <Text $variant="body" $size="md">
                  {t("cascade.triggerSource", {
                    source: getTriggerSourceLabel(
                      lastCascade.trigger_source,
                      t,
                    ),
                  })}
                </Text>
              </HistoryEntryLeft>
              <HistoryEntryRight>
                <Badge $variant={getStatusBadgeVariant(lastCascade.status)}>
                  {t(getStatusTranslationKey(lastCascade.status))}
                </Badge>
                <HistoryEntryMeta>
                  {lastCascade.completed_at
                    ? formatRelativeTime(lastCascade.completed_at)
                    : formatRelativeTime(lastCascade.created_at)}
                </HistoryEntryMeta>
              </HistoryEntryRight>
            </HistoryEntryHeader>
            {expandedHistoryId === lastCascade.id && (
              <CascadeDetailPanel
                detail={historyDetails[lastCascade.id]}
                t={t}
              />
            )}
          </HistoryEntry>
        </>
      )}

      {/* History list */}
      {historyItems.length > 1 && (
        <>
          <SectionHeading>{t("cascade.historyHeading")}</SectionHeading>
          {historyItems.slice(1).map((item) => (
            <HistoryEntry
              key={item.id}
              onClick={() => onHistoryClick(item.id)}
            >
              <HistoryEntryHeader>
                <HistoryEntryLeft>
                  <LayerBadge $layerSlug={item.starting_layer}>
                    {t(
                      LAYER_NAME_KEYS[item.starting_layer] ??
                        item.starting_layer,
                    )}
                  </LayerBadge>
                  <Text $variant="body" $size="sm">
                    {t("cascade.triggerSource", {
                      source: getTriggerSourceLabel(item.trigger_source, t),
                    })}
                  </Text>
                </HistoryEntryLeft>
                <HistoryEntryRight>
                  <Badge $variant={getStatusBadgeVariant(item.status)}>
                    {t(getStatusTranslationKey(item.status))}
                  </Badge>
                  <HistoryEntryMeta>
                    {item.completed_at && item.created_at
                      ? formatDuration(item.created_at, item.completed_at)
                      : formatRelativeTime(item.created_at)}
                  </HistoryEntryMeta>
                </HistoryEntryRight>
              </HistoryEntryHeader>
              {expandedHistoryId === item.id && (
                <CascadeDetailPanel
                  detail={historyDetails[item.id]}
                  t={t}
                />
              )}
            </HistoryEntry>
          ))}
        </>
      )}
    </HistorySection>
  );
}

/** Expanded detail for a history entry */
function CascadeDetailPanel({
  detail,
  t,
}: {
  detail: CascadeDetail | undefined;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  if (!detail) {
    return (
      <HistoryDetail>
        <Text $variant="muted" $size="sm">
          {t("common.loading")}
        </Text>
      </HistoryDetail>
    );
  }

  const uniqueLayers = [...new Set(detail.agent_runs.map((r) => r.target_layer))];

  return (
    <HistoryDetail onClick={(e: React.MouseEvent) => e.stopPropagation()}>
      <div>
        {t("cascade.triggerSource", {
          source: getTriggerSourceLabel(detail.trigger_source, t),
        })}
      </div>
      <div>
        {t("cascade.startedAt", {
          time: formatRelativeTime(detail.created_at),
        })}
        {detail.completed_at && (
          <>
            {" \u2014 "}
            {t("cascade.duration", {
              duration: formatDuration(detail.created_at, detail.completed_at),
            })}
          </>
        )}
      </div>
      {detail.error_message && (
        <div>
          {t("cascade.errorMessage", { message: detail.error_message })}
        </div>
      )}
      {uniqueLayers.length > 0 && (
        <div>
          {t("cascade.layersProcessed", {
            count: String(uniqueLayers.length),
          })}
          {" \u2014 "}
          {uniqueLayers.map((slug) => (
            <LayerBadge
              key={slug}
              $layerSlug={slug}
              style={{ marginRight: 4, marginBottom: 2 }}
            >
              {t(LAYER_NAME_KEYS[slug] ?? slug)}
            </LayerBadge>
          ))}
        </div>
      )}
    </HistoryDetail>
  );
}

/** Queue section showing waiting cascades */
function CascadeQueueSection({
  entries,
  removingId,
  onRemove,
  t,
}: {
  entries: QueueEntryData[];
  removingId: string | null;
  onRemove: (id: string) => void;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  return (
    <QueueSection>
      <SectionHeading>{t("cascade.queueHeading")}</SectionHeading>
      {entries.map((entry, idx) => (
        <QueueEntry key={entry.id}>
          <QueueEntryInfo>
            <QueueEntryTitle>
              {t("cascade.queuePosition", { position: String(idx + 1) })}
              {" \u2014 "}
              {getTriggerSourceLabel(entry.trigger_source, t)}
            </QueueEntryTitle>
            <QueueEntryMeta>
              <LayerBadge
                $layerSlug={entry.starting_layer}
                style={{ marginRight: 8 }}
              >
                {t(
                  LAYER_NAME_KEYS[entry.starting_layer] ??
                    entry.starting_layer,
                )}
              </LayerBadge>
              {t("cascade.queuedAt", {
                time: formatRelativeTime(entry.queued_at),
              })}
            </QueueEntryMeta>
          </QueueEntryInfo>
          <Button
            $variant="ghost"
            $size="sm"
            $loading={removingId === entry.id}
            onClick={(e: React.MouseEvent) => {
              e.stopPropagation();
              onRemove(entry.id);
            }}
          >
            {t("cascade.removeFromQueue")}
          </Button>
        </QueueEntry>
      ))}
    </QueueSection>
  );
}
