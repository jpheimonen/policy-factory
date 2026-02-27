/**
 * Stack Overview page — the authenticated home page.
 *
 * Displays the five-layer policy model as a vertical stack of cards.
 * Cards are ordered bottom (Values) to top (Policies) to mirror the
 * conceptual hierarchy. Each card shows:
 * - Layer name with identity colour accent
 * - Item count
 * - Last updated as human-readable relative time
 * - Narrative summary preview (truncated to ~2 lines)
 * - Pending feedback memo count badge (only when > 0)
 *
 * Clicking a card navigates to /layers/:layerSlug.
 *
 * Handles loading state (skeleton placeholders) and error state (message + retry).
 */
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "@/i18n/index.ts";
import { useLayerStore } from "@/stores/layerStore.ts";
import { Badge, Button, Text } from "@/components/atoms/index.ts";
import {
  PageWrapper,
  PageTitle,
  LayerStack,
  LayerCard,
  LayerCardHeader,
  LayerName,
  LayerMeta,
  MetaItem,
  NarrativePreview,
  SkeletonCard,
  SkeletonLine,
  ErrorWrapper,
} from "./StackOverviewPage.styles.ts";

// ── Relative time helper ─────────────────────────────────────────────

/**
 * Format an ISO timestamp as a human-readable relative time string.
 * Uses a simple approach without external dependencies.
 */
function formatRelativeTime(isoTimestamp: string): string {
  if (!isoTimestamp) return "";

  try {
    const date = new Date(isoTimestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffSeconds = Math.floor(diffMs / 1000);
    const diffMinutes = Math.floor(diffSeconds / 60);
    const diffHours = Math.floor(diffMinutes / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffSeconds < 60) return "just now";
    if (diffMinutes < 60) return `${diffMinutes}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return "yesterday";
    if (diffDays < 30) return `${diffDays}d ago`;

    // For older dates, show the date
    return date.toLocaleDateString();
  } catch {
    return "";
  }
}

// ── Layer name lookup ────────────────────────────────────────────────

const LAYER_NAME_KEYS: Record<string, string> = {
  values: "stackOverview.layerValues",
  "situational-awareness": "stackOverview.layerSituationalAwareness",
  "strategic-objectives": "stackOverview.layerStrategicObjectives",
  "tactical-objectives": "stackOverview.layerTacticalObjectives",
  policies: "stackOverview.layerPolicies",
};

// ── Skeleton loading component ───────────────────────────────────────

function LayerCardSkeleton() {
  return (
    <SkeletonCard>
      <SkeletonLine $width="40%" $height="20px" />
      <SkeletonLine $width="100%" $height="14px" />
      <SkeletonLine $width="70%" $height="14px" />
    </SkeletonCard>
  );
}

// ── Page component ───────────────────────────────────────────────────

export function StackOverviewPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const layers = useLayerStore((s) => s.layers);
  const loading = useLayerStore((s) => s.loading);
  const error = useLayerStore((s) => s.error);
  const init = useLayerStore((s) => s.init);
  const fetchLayers = useLayerStore((s) => s.fetchLayers);
  const refresh = useLayerStore((s) => s.refresh);
  const initialized = useLayerStore((s) => s.initialized);

  // Fetch layers on mount
  useEffect(() => {
    init();
  }, [init]);

  // Refresh when navigating back to this page (after initial load)
  useEffect(() => {
    if (initialized && !loading) {
      refresh();
    }
    // Only run on mount — the `initialized` check prevents double-fetch
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Loading state
  if (loading && layers.length === 0) {
    return (
      <PageWrapper>
        <PageTitle>{t("stackOverview.title")}</PageTitle>
        <LayerStack>
          {Array.from({ length: 5 }).map((_, i) => (
            <LayerCardSkeleton key={i} />
          ))}
        </LayerStack>
      </PageWrapper>
    );
  }

  // Error state
  if (error && layers.length === 0) {
    return (
      <PageWrapper>
        <PageTitle>{t("stackOverview.title")}</PageTitle>
        <ErrorWrapper>
          <Text $variant="muted" $size="md">
            {t("stackOverview.loadError")}
          </Text>
          <Text $variant="caption" $size="sm">
            {error}
          </Text>
          <Button $variant="secondary" $size="sm" onClick={() => fetchLayers()}>
            {t("stackOverview.retryButton")}
          </Button>
        </ErrorWrapper>
      </PageWrapper>
    );
  }

  return (
    <PageWrapper>
      <PageTitle>{t("stackOverview.title")}</PageTitle>
      <LayerStack>
        {layers.map((layer) => {
          const nameKey = LAYER_NAME_KEYS[layer.slug];
          const displayName = nameKey ? t(nameKey) : layer.display_name;
          const relativeTime = formatRelativeTime(layer.last_updated);

          return (
            <LayerCard
              key={layer.slug}
              $layerSlug={layer.slug}
              onClick={() => navigate(`/layers/${layer.slug}`)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  navigate(`/layers/${layer.slug}`);
                }
              }}
            >
              <LayerCardHeader>
                <LayerName $layerSlug={layer.slug}>{displayName}</LayerName>
                <LayerMeta>
                  <MetaItem>
                    {layer.item_count > 0
                      ? t("stackOverview.itemCount", {
                          count: String(layer.item_count),
                        })
                      : t("stackOverview.noItems")}
                  </MetaItem>
                  {relativeTime && (
                    <MetaItem>
                      {t("stackOverview.lastUpdated", { time: relativeTime })}
                    </MetaItem>
                  )}
                  {!relativeTime && layer.last_updated === "" && (
                    <MetaItem>{t("stackOverview.neverUpdated")}</MetaItem>
                  )}
                  {layer.pending_feedback_count > 0 && (
                    <Badge $variant="warning">
                      {t("stackOverview.feedbackMemoCount", {
                        count: String(layer.pending_feedback_count),
                      })}
                    </Badge>
                  )}
                </LayerMeta>
              </LayerCardHeader>
              <NarrativePreview>
                {layer.narrative_preview || t("stackOverview.noNarrativeSummary")}
              </NarrativePreview>
            </LayerCard>
          );
        })}
      </LayerStack>
    </PageWrapper>
  );
}
