/**
 * Version History page.
 *
 * Route: /history/:layerSlug
 *
 * Displays per-layer git commit history in a vertical timeline.
 * Each entry shows the commit timestamp, message, short hash, and author.
 *
 * Fetches data from `GET /api/history/:layerSlug` on mount.
 * Supports pagination via a "Load more" button.
 */
import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useTranslation } from "@/i18n/index.ts";
import { isValidLayerSlug } from "@/stores/layerStore.ts";
import { LAYER_NAME_KEYS } from "@/lib/layerConstants.ts";
import { apiRequest } from "@/lib/apiClient.ts";
import { formatRelativeTime } from "@/lib/timeUtils.ts";
import { Button } from "@/components/atoms/index.ts";
import { LoadingState, ErrorState, EmptyState } from "@/components/molecules/index.ts";
import {
  PageWrapper,
  PageHeader,
  HeaderLeft,
  BackLink,
  LayerTitle,
  CommitList,
  CommitEntry,
  CommitContent,
  CommitMessage,
  CommitMeta,
  CommitTimestamp,
  CommitHash,
  CommitAuthor,
  LoadMoreWrapper,
} from "./HistoryPage.styles.ts";

// ── Types ────────────────────────────────────────────────────────────

interface GitCommit {
  hash: string;
  timestamp: string;
  message: string;
  author: string;
}

// ── Time formatting helpers ──────────────────────────────────────────

function formatAbsoluteDate(isoTimestamp: string): string {
  if (!isoTimestamp) return "";
  try {
    const date = new Date(isoTimestamp);
    const day = date.getDate();
    const months = [
      "Jan", "Feb", "Mar", "Apr", "May", "Jun",
      "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ];
    const month = months[date.getMonth()];
    const year = date.getFullYear();
    const hours = String(date.getHours()).padStart(2, "0");
    const minutes = String(date.getMinutes()).padStart(2, "0");
    return `${day} ${month} ${year}, ${hours}:${minutes}`;
  } catch {
    return "";
  }
}

// ── Constants ────────────────────────────────────────────────────────

const DEFAULT_LIMIT = 20;

// ── Page component ───────────────────────────────────────────────────

export function HistoryPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { slug } = useParams<{ slug: string }>();

  // ── Local state ────────────────────────────────────────────────────
  const [commits, setCommits] = useState<GitCommit[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);

  // ── Fetch commits ──────────────────────────────────────────────────

  const fetchCommits = useCallback(
    async (limit: number, append: boolean) => {
      if (!slug) return;

      try {
        const params = new URLSearchParams();
        params.set("limit", String(limit));
        if (append && commits.length > 0) {
          // Use offset-based pagination
          params.set("offset", String(commits.length));
        }

        const data = await apiRequest<GitCommit[]>(
          `/api/history/${slug}?${params.toString()}`,
        );

        if (append) {
          setCommits((prev) => [...prev, ...data]);
        } else {
          setCommits(data);
        }

        // If fewer commits returned than requested, no more to load
        if (data.length < limit) {
          setHasMore(false);
        }

        setError(null);
      } catch {
        setError(t("history.loadError"));
      }
    },
    [slug, commits.length, t],
  );

  // ── Initial load ───────────────────────────────────────────────────

  useEffect(() => {
    if (!slug || !isValidLayerSlug(slug)) {
      setLoading(false);
      return;
    }

    const load = async () => {
      setLoading(true);
      setHasMore(true);
      setCommits([]);
      await fetchCommits(DEFAULT_LIMIT, false);
      setLoading(false);
    };
    load();
    // Only run on slug change, not on fetchCommits reference change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  // ── Handlers ───────────────────────────────────────────────────────

  const handleBack = useCallback(() => {
    navigate(`/layers/${slug}`);
  }, [navigate, slug]);

  const handleLoadMore = useCallback(async () => {
    if (loadingMore) return;
    setLoadingMore(true);
    await fetchCommits(DEFAULT_LIMIT, true);
    setLoadingMore(false);
  }, [fetchCommits, loadingMore]);

  const handleRetry = useCallback(async () => {
    setLoading(true);
    setError(null);
    setHasMore(true);
    setCommits([]);
    await fetchCommits(DEFAULT_LIMIT, false);
    setLoading(false);
  }, [fetchCommits]);

  // ── Invalid slug ───────────────────────────────────────────────────

  if (!slug || !isValidLayerSlug(slug)) {
    return (
      <PageWrapper>
        <ErrorState
          message={t("history.invalidLayer", { slug: slug ?? "" })}
          onRetry={() => navigate("/")}
        />
      </PageWrapper>
    );
  }

  // ── Computed values ────────────────────────────────────────────────

  const layerNameKey = LAYER_NAME_KEYS[slug] ?? slug;
  const layerDisplayName = t(layerNameKey);

  // ── Loading state ──────────────────────────────────────────────────

  if (loading) {
    return (
      <PageWrapper>
        <PageHeader $layerSlug={slug}>
          <HeaderLeft>
            <BackLink onClick={handleBack}>
              &larr; {t("history.backToLayer", { layerName: layerDisplayName })}
            </BackLink>
            <LayerTitle $layerSlug={slug}>
              {t("history.title", { layerName: layerDisplayName })}
            </LayerTitle>
          </HeaderLeft>
        </PageHeader>
        <LoadingState message={t("history.loadingHistory")} />
      </PageWrapper>
    );
  }

  // ── Error state ────────────────────────────────────────────────────

  if (error) {
    return (
      <PageWrapper>
        <PageHeader $layerSlug={slug}>
          <HeaderLeft>
            <BackLink onClick={handleBack}>
              &larr; {t("history.backToLayer", { layerName: layerDisplayName })}
            </BackLink>
            <LayerTitle $layerSlug={slug}>
              {t("history.title", { layerName: layerDisplayName })}
            </LayerTitle>
          </HeaderLeft>
        </PageHeader>
        <ErrorState message={error} onRetry={handleRetry} />
      </PageWrapper>
    );
  }

  // ── Content ────────────────────────────────────────────────────────

  return (
    <PageWrapper>
      {/* ── Page header ──────────────────────────────────────── */}
      <PageHeader $layerSlug={slug}>
        <HeaderLeft>
          <BackLink onClick={handleBack}>
            &larr; {t("history.backToLayer", { layerName: layerDisplayName })}
          </BackLink>
          <LayerTitle $layerSlug={slug}>
            {t("history.title", { layerName: layerDisplayName })}
          </LayerTitle>
        </HeaderLeft>
      </PageHeader>

      {/* ── Commit list ──────────────────────────────────────── */}
      {commits.length === 0 ? (
        <EmptyState
          title={t("history.noHistory")}
          icon="\uD83D\uDCC4"
        />
      ) : (
        <>
          <CommitList>
            {commits.map((commit) => {
              const absoluteDate = formatAbsoluteDate(commit.timestamp);
              const relativeTime = formatRelativeTime(commit.timestamp);
              const shortHash = commit.hash.slice(0, 7);

              return (
                <CommitEntry key={commit.hash} $layerSlug={slug}>
                  <CommitContent>
                    <CommitMessage>{commit.message}</CommitMessage>
                    <CommitMeta>
                      <CommitTimestamp title={commit.timestamp}>
                        {absoluteDate}
                        {relativeTime && ` (${relativeTime})`}
                      </CommitTimestamp>
                      <CommitHash>{shortHash}</CommitHash>
                      {commit.author && (
                        <CommitAuthor>{commit.author}</CommitAuthor>
                      )}
                    </CommitMeta>
                  </CommitContent>
                </CommitEntry>
              );
            })}
          </CommitList>

          {/* Load more button */}
          {hasMore && (
            <LoadMoreWrapper>
              <Button
                $variant="ghost"
                $size="sm"
                $loading={loadingMore}
                onClick={handleLoadMore}
                disabled={loadingMore}
              >
                {loadingMore
                  ? t("history.loadingMore")
                  : t("history.loadMore")}
              </Button>
            </LoadMoreWrapper>
          )}
        </>
      )}
    </PageWrapper>
  );
}
