/**
 * Heartbeat Log page.
 *
 * Route: /heartbeat
 *
 * Shows heartbeat run history with three levels of detail:
 *   Level 1 — Run list: trigger type, highest tier, time, outcome
 *   Level 2 — Tier detail: tier-by-tier breakdown when a run is expanded
 *   Level 3 — Transcript: on-demand agent output text per tier
 *
 * Data sources:
 *   - GET /api/heartbeat/history (run list with pagination)
 *   - GET /api/heartbeat/agent-run/{id} (transcript on demand)
 *
 * Follows the CascadePage expandable-detail and HistoryPage pagination patterns.
 */
import { useEffect, useState, useCallback, useRef } from "react";
import { useTranslation } from "@/i18n/index.ts";
import { apiRequest } from "@/lib/apiClient.ts";
import { formatRelativeTime } from "@/lib/timeUtils.ts";
import { Badge, Button, Text } from "@/components/atoms/index.ts";
import { LoadingState, ErrorState, EmptyState } from "@/components/molecules/index.ts";
import {
  PageWrapper,
  PageHeader,
  HeaderLeft,
  RunList,
  RunEntry,
  RunEntryHeader,
  RunEntryLeft,
  RunEntryRight,
  RunEntryMeta,
  RunDetail,
  TierEntry,
  TierHeader,
  TierLeft,
  TierRight,
  TierLabel,
  TierOutcome,
  TranscriptToggle,
  TranscriptContainer,
  TranscriptText,
  TranscriptMessage,
  OutcomeBadge,
  LoadMoreWrapper,
} from "./HeartbeatLogPage.styles.ts";

// ── Constants ────────────────────────────────────────────────────────

const PAGE_SIZE = 20;

// ── API types ────────────────────────────────────────────────────────

interface TierEntryData {
  tier: number;
  escalated: boolean;
  outcome: string | null;
  agent_run_id: string | null;
  started_at: string | null;
  ended_at: string | null;
}

interface HeartbeatRunData {
  id: string;
  trigger: string;
  started_at: string;
  completed_at: string | null;
  highest_tier: number;
  structured_log: TierEntryData[];
}

interface AgentRunData {
  id: string;
  agent_type: string;
  agent_label: string;
  model: string;
  target_layer: string | null;
  started_at: string;
  completed_at: string | null;
  success: boolean;
  error_message: string | null;
  cost_usd: number;
  output_text: string | null;
}

// ── Utility functions ────────────────────────────────────────────────

const TIER_LABEL_KEYS: Record<number, string> = {
  1: "heartbeat.tierSkim",
  2: "heartbeat.tierTriage",
  3: "heartbeat.tierSaUpdateLabel",
  4: "heartbeat.tierCascade",
};

function formatDuration(start: string, end: string): string {
  const diffMs = new Date(end).getTime() - new Date(start).getTime();
  const diffSec = Math.floor(diffMs / 1000);
  if (diffSec < 60) return `${diffSec}s`;
  const min = Math.floor(diffSec / 60);
  const sec = diffSec % 60;
  return `${min}m ${sec}s`;
}

/**
 * Derive a human-readable outcome label and badge variant from a heartbeat run.
 *
 * Logic:
 *   - Any tier with an error → "failed"
 *   - Tier 4 reached → "cascade triggered"
 *   - Tier 3 completed successfully → "update made"
 *   - Tier 1 or 2 reached, did not escalate → "nothing noteworthy"
 *   - Fallback → show raw tier and status
 */
function deriveOutcome(
  run: HeartbeatRunData,
  t: (key: string) => string,
): { label: string; variant: "neutral" | "success" | "warning" | "error" } {
  const log = run.structured_log;

  // Check for any failed tier
  const hasFailed = log.some(
    (entry) =>
      entry.outcome !== null &&
      entry.outcome.toLowerCase().includes("error"),
  );
  if (hasFailed) {
    return { label: t("heartbeat.outcomeFailed"), variant: "error" };
  }

  if (run.highest_tier >= 4) {
    return { label: t("heartbeat.outcomeCascadeTriggered"), variant: "warning" };
  }

  if (run.highest_tier >= 3) {
    return { label: t("heartbeat.outcomeUpdateMade"), variant: "success" };
  }

  // Tiers 1-2: nothing noteworthy
  if (run.highest_tier >= 1) {
    return { label: t("heartbeat.outcomeNothingNoteworthy"), variant: "neutral" };
  }

  // Fallback
  return {
    label: `Tier ${run.highest_tier}`,
    variant: "neutral",
  };
}

// ── Component ────────────────────────────────────────────────────────

export function HeartbeatLogPage() {
  const { t } = useTranslation();

  // ── State ──────────────────────────────────────────────────────────
  const [runs, setRuns] = useState<HeartbeatRunData[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  // Expanded run (Level 2)
  const [expandedRunId, setExpandedRunId] = useState<string | null>(null);

  // Expanded transcripts (Level 3) — set of tier keys like "runId:tier"
  const [expandedTranscripts, setExpandedTranscripts] = useState<Set<string>>(
    new Set(),
  );

  // Cached transcript data — keyed by agent_run_id
  const transcriptCache = useRef<
    Record<string, { data: AgentRunData | null; error: boolean }>
  >({});

  // Loading transcripts — keyed by agent_run_id
  const [loadingTranscripts, setLoadingTranscripts] = useState<Set<string>>(
    new Set(),
  );

  // Force re-render when transcript cache updates
  const [, setTranscriptVersion] = useState(0);

  // ── Data fetching ──────────────────────────────────────────────────

  const fetchRuns = useCallback(
    async (offset: number, append: boolean) => {
      try {
        const params = new URLSearchParams();
        params.set("limit", String(PAGE_SIZE));
        params.set("offset", String(offset));

        const data = await apiRequest<HeartbeatRunData[]>(
          `/api/heartbeat/history?${params.toString()}`,
        );

        if (append) {
          setRuns((prev) => [...prev, ...data]);
        } else {
          setRuns(data);
        }

        if (data.length < PAGE_SIZE) {
          setHasMore(false);
        }

        setError(null);
      } catch {
        setError(t("heartbeat.loadError"));
      }
    },
    [t],
  );

  const fetchTranscript = useCallback(
    async (agentRunId: string) => {
      // Already cached
      if (transcriptCache.current[agentRunId]) return;

      setLoadingTranscripts((prev) => new Set(prev).add(agentRunId));

      try {
        const data = await apiRequest<AgentRunData>(
          `/api/heartbeat/agent-run/${agentRunId}`,
        );
        transcriptCache.current[agentRunId] = { data, error: false };
      } catch {
        transcriptCache.current[agentRunId] = { data: null, error: true };
      } finally {
        setLoadingTranscripts((prev) => {
          const next = new Set(prev);
          next.delete(agentRunId);
          return next;
        });
        setTranscriptVersion((v) => v + 1);
      }
    },
    [],
  );

  // ── Initial load ───────────────────────────────────────────────────

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      await fetchRuns(0, false);
      setLoading(false);
    };
    load();
    // Only run once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Handlers ───────────────────────────────────────────────────────

  const handleRunClick = useCallback((id: string) => {
    setExpandedRunId((prev) => (prev === id ? null : id));
  }, []);

  const handleTranscriptToggle = useCallback(
    (tierKey: string, agentRunId: string) => {
      setExpandedTranscripts((prev) => {
        const next = new Set(prev);
        if (next.has(tierKey)) {
          next.delete(tierKey);
        } else {
          next.add(tierKey);
          // Fetch transcript if not cached
          fetchTranscript(agentRunId);
        }
        return next;
      });
    },
    [fetchTranscript],
  );

  const handleLoadMore = useCallback(async () => {
    if (loadingMore) return;
    setLoadingMore(true);
    await fetchRuns(runs.length, true);
    setLoadingMore(false);
  }, [fetchRuns, loadingMore, runs.length]);

  const handleRetry = useCallback(async () => {
    setLoading(true);
    setError(null);
    setHasMore(true);
    setRuns([]);
    await fetchRuns(0, false);
    setLoading(false);
  }, [fetchRuns]);

  // ── Render: Loading state ──────────────────────────────────────────

  if (loading) {
    return (
      <PageWrapper>
        <PageHeader>
          <HeaderLeft>
            <Text as="h1" $variant="heading" $size="xl">
              {t("heartbeat.pageTitle")}
            </Text>
          </HeaderLeft>
        </PageHeader>
        <LoadingState />
      </PageWrapper>
    );
  }

  // ── Render: Error state ────────────────────────────────────────────

  if (error) {
    return (
      <PageWrapper>
        <PageHeader>
          <HeaderLeft>
            <Text as="h1" $variant="heading" $size="xl">
              {t("heartbeat.pageTitle")}
            </Text>
          </HeaderLeft>
        </PageHeader>
        <ErrorState message={error} onRetry={handleRetry} />
      </PageWrapper>
    );
  }

  // ── Render: Empty state ────────────────────────────────────────────

  if (runs.length === 0) {
    return (
      <PageWrapper>
        <PageHeader>
          <HeaderLeft>
            <Text as="h1" $variant="heading" $size="xl">
              {t("heartbeat.pageTitle")}
            </Text>
          </HeaderLeft>
        </PageHeader>
        <EmptyState title={t("heartbeat.logEmpty")} />
      </PageWrapper>
    );
  }

  // ── Render: Run list ───────────────────────────────────────────────

  return (
    <PageWrapper>
      <PageHeader>
        <HeaderLeft>
          <Text as="h1" $variant="heading" $size="xl">
            {t("heartbeat.pageTitle")}
          </Text>
        </HeaderLeft>
      </PageHeader>

      <RunList>
        {runs.map((run) => {
          const outcome = deriveOutcome(run, t);
          const isExpanded = expandedRunId === run.id;
          const triggerLabel =
            run.trigger === "manual"
              ? t("heartbeat.triggerManual")
              : t("heartbeat.triggerScheduled");
          const duration =
            run.completed_at
              ? formatDuration(run.started_at, run.completed_at)
              : null;

          return (
            <RunEntry key={run.id} onClick={() => handleRunClick(run.id)}>
              <RunEntryHeader>
                <RunEntryLeft>
                  <Badge $variant="neutral">{triggerLabel}</Badge>
                  <Text $variant="body" $size="sm">
                    {t("heartbeat.tierReached", {
                      tier: String(run.highest_tier),
                    })}
                  </Text>
                  <OutcomeBadge $variant={outcome.variant}>
                    {outcome.label}
                  </OutcomeBadge>
                </RunEntryLeft>
                <RunEntryRight>
                  {duration && (
                    <RunEntryMeta>
                      {t("heartbeat.duration", { duration })}
                    </RunEntryMeta>
                  )}
                  <RunEntryMeta>
                    {formatRelativeTime(run.started_at)}
                  </RunEntryMeta>
                </RunEntryRight>
              </RunEntryHeader>

              {isExpanded && (
                <HeartbeatRunDetail
                  run={run}
                  expandedTranscripts={expandedTranscripts}
                  loadingTranscripts={loadingTranscripts}
                  transcriptCache={transcriptCache.current}
                  onTranscriptToggle={handleTranscriptToggle}
                  t={t}
                />
              )}
            </RunEntry>
          );
        })}
      </RunList>

      {hasMore && (
        <LoadMoreWrapper>
          <Button
            $variant="ghost"
            $size="sm"
            $loading={loadingMore}
            onClick={(e: React.MouseEvent) => {
              e.stopPropagation();
              handleLoadMore();
            }}
            disabled={loadingMore}
          >
            {loadingMore
              ? t("heartbeat.loadingMore")
              : t("heartbeat.loadMore")}
          </Button>
        </LoadMoreWrapper>
      )}
    </PageWrapper>
  );
}

// ── Sub-components ───────────────────────────────────────────────────

/** Expanded detail for a heartbeat run showing tier-by-tier breakdown */
function HeartbeatRunDetail({
  run,
  expandedTranscripts,
  loadingTranscripts,
  transcriptCache,
  onTranscriptToggle,
  t,
}: {
  run: HeartbeatRunData;
  expandedTranscripts: Set<string>;
  loadingTranscripts: Set<string>;
  transcriptCache: Record<
    string,
    { data: AgentRunData | null; error: boolean }
  >;
  onTranscriptToggle: (tierKey: string, agentRunId: string) => void;
  t: (key: string, params?: Record<string, string>) => string;
}) {
  return (
    <RunDetail onClick={(e: React.MouseEvent) => e.stopPropagation()}>
      {run.structured_log.map((tier) => {
        const tierKey = `${run.id}:${tier.tier}`;
        const tierLabelKey = TIER_LABEL_KEYS[tier.tier] ?? `Tier ${tier.tier}`;
        const isTranscriptExpanded = expandedTranscripts.has(tierKey);
        const duration =
          tier.started_at && tier.ended_at
            ? formatDuration(tier.started_at, tier.ended_at)
            : null;

        return (
          <TierEntry key={tier.tier}>
            <TierHeader>
              <TierLeft>
                <TierLabel>
                  {TIER_LABEL_KEYS[tier.tier]
                    ? t(tierLabelKey)
                    : tierLabelKey}
                </TierLabel>
                <Badge $variant={tier.escalated ? "info" : "neutral"}>
                  {tier.escalated
                    ? t("heartbeat.escalated")
                    : t("heartbeat.notEscalated")}
                </Badge>
              </TierLeft>
              <TierRight>
                {duration && (
                  <span>{t("heartbeat.duration", { duration })}</span>
                )}
              </TierRight>
            </TierHeader>

            {tier.outcome && (
              <TierOutcome>{tier.outcome}</TierOutcome>
            )}

            {tier.agent_run_id && (
              <>
                <TranscriptToggle
                  onClick={(e: React.MouseEvent) => {
                    e.stopPropagation();
                    onTranscriptToggle(tierKey, tier.agent_run_id!);
                  }}
                >
                  {isTranscriptExpanded
                    ? `▾ ${t("heartbeat.collapseTranscript")}`
                    : `▸ ${t("heartbeat.expandTranscript")}`}
                </TranscriptToggle>

                {isTranscriptExpanded && (
                  <TranscriptView
                    isLoading={loadingTranscripts.has(tier.agent_run_id)}
                    cached={transcriptCache[tier.agent_run_id]}
                    t={t}
                  />
                )}
              </>
            )}
          </TierEntry>
        );
      })}
    </RunDetail>
  );
}

/** On-demand transcript display for a single tier's agent run */
function TranscriptView({
  isLoading,
  cached,
  t,
}: {
  isLoading: boolean;
  cached?: { data: AgentRunData | null; error: boolean };
  t: (key: string) => string;
}) {
  if (isLoading || !cached) {
    return (
      <TranscriptMessage>{t("heartbeat.transcriptLoading")}</TranscriptMessage>
    );
  }

  if (cached.error) {
    return (
      <TranscriptMessage>{t("heartbeat.transcriptError")}</TranscriptMessage>
    );
  }

  if (!cached.data?.output_text) {
    return (
      <TranscriptMessage>{t("heartbeat.transcriptEmpty")}</TranscriptMessage>
    );
  }

  return (
    <TranscriptContainer>
      <TranscriptText>{cached.data.output_text}</TranscriptText>
    </TranscriptContainer>
  );
}
