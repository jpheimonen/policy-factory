/**
 * Layer Detail page.
 *
 * Route: /layers/:layerSlug
 *
 * Displays the full detail view for a single policy layer:
 * - Page header with layer name, identity colour accent, back link, and refresh button
 * - Narrative summary rendered as markdown
 * - Pending feedback memos with accept/dismiss actions
 * - All items as clickable cards with frontmatter metadata
 * - Critic assessment summary section (placeholder until steps 015-016)
 *
 * The page fetches items and summary in parallel via the layer store.
 * Loading and error states are handled with reusable molecule components.
 */
import { useEffect, useCallback, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "@/i18n/index.ts";
import { useLayerStore, isValidLayerSlug } from "@/stores/layerStore.ts";
import type { LayerItem, FeedbackMemo } from "@/stores/layerStore.ts";
import { LAYER_NAME_KEYS } from "@/lib/layerConstants.ts";
import { apiRequest } from "@/lib/apiClient.ts";
import { formatRelativeTime } from "@/lib/timeUtils.ts";
import { Badge, Button, Markdown } from "@/components/atoms/index.ts";
import { LoadingState, ErrorState, EmptyState } from "@/components/molecules/index.ts";
import {
  PageWrapper,
  PageHeader,
  HeaderLeft,
  HeaderRight,
  BackLink,
  LayerTitle,
  Section,
  SectionHeader,
  SectionTitle,
  SummaryWrapper,
  MemoCard,
  MemoSource,
  MemoContent,
  MemoActions,
  ItemCardList,
  ItemCard,
  ItemHeader,
  ItemTitle,
  ItemMeta,
  MetaItem,
  CriticPlaceholder,
  CriticPlaceholderText,
} from "./LayerDetailPage.styles.ts";

// ── Item slug helper ─────────────────────────────────────────────────

/** Convert a filename to a slug for URL navigation (strips .md extension). */
function filenameToSlug(filename: string): string {
  return filename.replace(/\.md$/, "");
}

// ── Page component ───────────────────────────────────────────────────

export function LayerDetailPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { slug } = useParams<{ slug: string }>();

  // Store selectors
  const detailItems = useLayerStore((s) => s.detailItems);
  const detailSummary = useLayerStore((s) => s.detailSummary);
  const detailMemos = useLayerStore((s) => s.detailMemos);
  const detailLoading = useLayerStore((s) => s.detailLoading);
  const detailError = useLayerStore((s) => s.detailError);
  const fetchLayerDetail = useLayerStore((s) => s.fetchLayerDetail);
  const clearLayerDetail = useLayerStore((s) => s.clearLayerDetail);

  // Local state
  const [refreshing, setRefreshing] = useState(false);
  const [dismissedMemoIds, setDismissedMemoIds] = useState<Set<string>>(
    new Set(),
  );

  // ── Fetch detail on mount / slug change ───────────────────────────

  useEffect(() => {
    if (slug && isValidLayerSlug(slug)) {
      fetchLayerDetail(slug);
    }

    return () => {
      clearLayerDetail();
    };
  }, [slug, fetchLayerDetail, clearLayerDetail]);

  // ── Handlers ──────────────────────────────────────────────────────

  const handleBack = useCallback(() => {
    navigate("/");
  }, [navigate]);

  const handleRefresh = useCallback(async () => {
    if (!slug || refreshing) return;
    setRefreshing(true);

    try {
      await apiRequest("/api/cascade/trigger", {
        method: "POST",
        body: { layer: slug, type: "layer_refresh" },
      });
    } catch {
      // Cascade endpoint is not yet available (step 017) — gracefully ignored.
      // The button simply returns to its idle state.
    } finally {
      setRefreshing(false);
    }
  }, [slug, refreshing]);

  const handleItemClick = useCallback(
    (item: LayerItem) => {
      navigate(`/layers/${slug}/${filenameToSlug(item.filename)}`);
    },
    [navigate, slug],
  );

  const handleAcceptMemo = useCallback(
    async (memo: FeedbackMemo) => {
      try {
        await apiRequest(`/api/layers/${slug}/feedback-memos/${memo.id}`, {
          method: "PUT",
          body: { status: "accepted" },
        });
      } catch {
        // Endpoint not available yet (step 017)
      }
      // Optimistic UI — remove from view
      setDismissedMemoIds((prev) => new Set([...prev, memo.id]));
    },
    [slug],
  );

  const handleDismissMemo = useCallback(
    async (memo: FeedbackMemo) => {
      try {
        await apiRequest(`/api/layers/${slug}/feedback-memos/${memo.id}`, {
          method: "PUT",
          body: { status: "dismissed" },
        });
      } catch {
        // Endpoint not available yet (step 017)
      }
      // Optimistic UI — remove from view
      setDismissedMemoIds((prev) => new Set([...prev, memo.id]));
    },
    [slug],
  );

  // ── Invalid slug ──────────────────────────────────────────────────

  if (!slug || !isValidLayerSlug(slug)) {
    return (
      <PageWrapper>
        <ErrorState
          message={t("layers.invalidLayer", { slug: slug ?? "" })}
          onRetry={handleBack}
        />
      </PageWrapper>
    );
  }

  // ── Loading state ─────────────────────────────────────────────────
  // Show full-page loading spinner when detail data is being fetched
  // and we don't have items to display yet (prevents blank page).

  if (detailLoading && detailItems.length === 0) {
    return (
      <PageWrapper>
        <LoadingState />
      </PageWrapper>
    );
  }

  // ── Error state ───────────────────────────────────────────────────

  if (detailError) {
    return (
      <PageWrapper>
        <PageHeader $layerSlug={slug}>
          <HeaderLeft>
            <BackLink onClick={handleBack}>
              &larr; {t("layers.backToHome")}
            </BackLink>
            <LayerTitle $layerSlug={slug}>
              {t(LAYER_NAME_KEYS[slug] ?? slug)}
            </LayerTitle>
          </HeaderLeft>
        </PageHeader>
        <ErrorState
          message={detailError}
          onRetry={() => fetchLayerDetail(slug)}
        />
      </PageWrapper>
    );
  }

  // ── Computed values ───────────────────────────────────────────────

  const layerDisplayName = t(LAYER_NAME_KEYS[slug] ?? slug);
  const visibleMemos = detailMemos.filter(
    (m) => m.status === "pending" && !dismissedMemoIds.has(m.id),
  );

  // ── Content ───────────────────────────────────────────────────────

  return (
    <PageWrapper>
      {/* ── Page header ──────────────────────────────────────────── */}
      <PageHeader $layerSlug={slug}>
        <HeaderLeft>
          <BackLink onClick={handleBack}>
            &larr; {t("layers.backToHome")}
          </BackLink>
          <LayerTitle $layerSlug={slug}>{layerDisplayName}</LayerTitle>
        </HeaderLeft>
        <HeaderRight>
          <Button
            $variant="ghost"
            $size="sm"
            onClick={() => navigate(`/history/${slug}`)}
          >
            {t("layers.versionHistory")}
          </Button>
          <Button
            $variant="secondary"
            $size="sm"
            $loading={refreshing}
            onClick={handleRefresh}
            disabled={refreshing}
          >
            {refreshing ? t("layers.refreshing") : t("layers.refreshButton")}
          </Button>
        </HeaderRight>
      </PageHeader>

      {/* ── Narrative summary section ────────────────────────────── */}
      <Section>
        <SectionTitle>{t("layers.narrativeSummary")}</SectionTitle>
        <SummaryWrapper>
          {detailSummary ? (
            <Markdown content={detailSummary} />
          ) : (
            <EmptyState title={t("layers.noSummaryYet")} compact />
          )}
        </SummaryWrapper>
      </Section>

      {/* ── Feedback memos section (hidden when empty) ───────────── */}
      {visibleMemos.length > 0 && (
        <Section>
          <SectionHeader>
            <SectionTitle>{t("layers.feedbackMemos")}</SectionTitle>
            <Badge $variant="warning">
              {t("layers.feedbackMemosCount", {
                count: String(visibleMemos.length),
              })}
            </Badge>
          </SectionHeader>
          {visibleMemos.map((memo) => {
            const sourceNameKey =
              LAYER_NAME_KEYS[memo.source_layer] ?? memo.source_layer;
            const sourceName = t(sourceNameKey);

            return (
              <MemoCard key={memo.id}>
                <MemoSource>
                  {t("layers.feedbackFrom", { layer: sourceName })}
                </MemoSource>
                <MemoContent>{memo.content}</MemoContent>
                <MemoActions>
                  <Button
                    $variant="primary"
                    $size="sm"
                    onClick={() => handleAcceptMemo(memo)}
                  >
                    {t("layers.feedbackAccept")}
                  </Button>
                  <Button
                    $variant="ghost"
                    $size="sm"
                    onClick={() => handleDismissMemo(memo)}
                  >
                    {t("layers.feedbackDismiss")}
                  </Button>
                </MemoActions>
              </MemoCard>
            );
          })}
        </Section>
      )}

      {/* ── Items section ────────────────────────────────────────── */}
      <Section>
        <SectionTitle>{t("layers.items")}</SectionTitle>
        {detailItems.length === 0 ? (
          <EmptyState title={t("layers.noItems")} icon="📄" compact />
        ) : (
          <ItemCardList>
            {detailItems.map((item) => {
              const relativeTime = formatRelativeTime(item.last_modified);

              return (
                <ItemCard
                  key={item.filename}
                  $layerSlug={slug}
                  onClick={() => handleItemClick(item)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      handleItemClick(item);
                    }
                  }}
                >
                  <ItemHeader>
                    <ItemTitle>{item.title || item.filename}</ItemTitle>
                    {item.status && (
                      <Badge
                        $variant={
                          item.status === "active"
                            ? "success"
                            : item.status === "draft"
                              ? "neutral"
                              : item.status === "archived"
                                ? "neutral"
                                : "info"
                        }
                      >
                        {item.status}
                      </Badge>
                    )}
                  </ItemHeader>
                  <ItemMeta>
                    {relativeTime && (
                      <MetaItem>
                        {t("common.lastUpdated", { time: relativeTime })}
                      </MetaItem>
                    )}
                    {item.last_modified_by && (
                      <MetaItem>
                        {t("layers.lastModifiedBy", {
                          user: item.last_modified_by,
                        })}
                      </MetaItem>
                    )}
                  </ItemMeta>
                </ItemCard>
              );
            })}
          </ItemCardList>
        )}
      </Section>

      {/* ── Critic assessment summary section ────────────────────── */}
      <Section>
        <SectionTitle>{t("layers.criticSummary")}</SectionTitle>
        <CriticPlaceholder>
          <CriticPlaceholderText>
            {t("layers.criticAssessmentEmpty")}
          </CriticPlaceholderText>
        </CriticPlaceholder>
      </Section>
    </PageWrapper>
  );
}
