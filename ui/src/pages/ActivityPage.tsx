/**
 * Activity Feed page.
 *
 * Route: /activity
 *
 * Displays a chronological stream of all system events with filtering
 * by event category and layer. New events appear in real-time via WebSocket
 * through the activity store (no direct WebSocket interaction needed).
 *
 * On mount, loads historical events from `GET /api/activity/` so users
 * see past activity even if they weren't connected when it happened.
 *
 * The activity store (step 013) handles all data management:
 * - `addEvent()` — called by the central WebSocket dispatcher
 * - `fetchHistory()` — loads historical events from the REST API
 * - `setFilter()` — updates category and layer filters
 * - `getFilteredEvents()` — returns events matching current filters
 */
import { useEffect, useCallback, useState, useRef, useMemo } from "react";
import { useTranslation } from "@/i18n/index.ts";
import { useActivityStore } from "@/stores/activityStore.ts";
import type { ActivityEvent } from "@/stores/activityStore.ts";
import { useLayerStore } from "@/stores/layerStore.ts";
import { Select, Button } from "@/components/atoms/index.ts";
import { LoadingState, ErrorState, EmptyState, EventItem } from "@/components/molecules/index.ts";
import type { EventCategory } from "@/types/events.ts";
import {
  PageWrapper,
  PageHeader,
  PageTitle,
  FilterBar,
  FilterGroup,
  FilterLabel,
  CategoryButtons,
  CategoryButton,
  EventList,
  LoadMoreWrapper,
} from "./ActivityPage.styles.ts";

// ── Constants ────────────────────────────────────────────────────────

const PAGE_SIZE = 50;

/** Event types that should not appear as individual items in the feed. */
const EXCLUDED_EVENT_TYPES = new Set(["agent_text_chunk"]);

/** Category filter options. */
const CATEGORY_OPTIONS: Array<{ value: EventCategory | "all"; labelKey: string }> = [
  { value: "all", labelKey: "activity.categoryAll" },
  { value: "cascade", labelKey: "activity.categoryCascade" },
  { value: "heartbeat", labelKey: "activity.categoryHeartbeat" },
  { value: "idea", labelKey: "activity.categoryIdeas" },
  { value: "system", labelKey: "activity.categorySystem" },
];

// ── Page component ───────────────────────────────────────────────────

export function ActivityPage() {
  const { t } = useTranslation();

  // ── Store selectors ────────────────────────────────────────────────
  const filterCategory = useActivityStore((s) => s.filterCategory);
  const filterLayer = useActivityStore((s) => s.filterLayer);
  const loading = useActivityStore((s) => s.loading);
  const error = useActivityStore((s) => s.error);
  const setFilter = useActivityStore((s) => s.setFilter);
  const fetchHistory = useActivityStore((s) => s.fetchHistory);
  const getFilteredEvents = useActivityStore((s) => s.getFilteredEvents);

  // Layer store for filter dropdown
  const layers = useLayerStore((s) => s.layers);
  const initLayers = useLayerStore((s) => s.init);

  // ── Local state ────────────────────────────────────────────────────
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasMore, setHasMore] = useState(true);
  const [offset, setOffset] = useState(0);
  const [initialLoaded, setInitialLoaded] = useState(false);

  // Track previously seen event IDs for "new" animation
  const prevEventIdsRef = useRef<Set<number>>(new Set());

  // ── Initialization ─────────────────────────────────────────────────

  useEffect(() => {
    initLayers();
  }, [initLayers]);

  useEffect(() => {
    const load = async () => {
      await fetchHistory(PAGE_SIZE, 0);
      setOffset(PAGE_SIZE);
      setInitialLoaded(true);
    };
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Filter handlers ────────────────────────────────────────────────

  const handleCategoryChange = useCallback(
    (category: EventCategory | "all") => {
      const newCategory = category === "all" ? null : category;
      setFilter(newCategory, filterLayer);
    },
    [filterLayer, setFilter],
  );

  const handleLayerChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const value = e.target.value;
      const newLayer = value === "all" ? null : value;
      setFilter(filterCategory, newLayer);
    },
    [filterCategory, setFilter],
  );

  // ── Load more ──────────────────────────────────────────────────────

  const handleLoadMore = useCallback(async () => {
    if (loadingMore) return;
    setLoadingMore(true);
    try {
      await fetchHistory(PAGE_SIZE, offset);
      setOffset((prev) => prev + PAGE_SIZE);
      // If fewer events were returned than requested, we've reached the end
      const currentEvents = useActivityStore.getState().events;
      if (currentEvents.length < offset + PAGE_SIZE) {
        setHasMore(false);
      }
    } catch {
      // Error handled by the store
    } finally {
      setLoadingMore(false);
    }
  }, [fetchHistory, offset, loadingMore]);

  // ── Retry ──────────────────────────────────────────────────────────

  const handleRetry = useCallback(async () => {
    setOffset(0);
    setHasMore(true);
    await fetchHistory(PAGE_SIZE, 0);
    setOffset(PAGE_SIZE);
  }, [fetchHistory]);

  // ── Filtered events ────────────────────────────────────────────────

  const filteredEvents = getFilteredEvents();

  // Filter out agent_text_chunk and reverse for newest-first display
  const displayEvents = useMemo(() => {
    const filtered = filteredEvents.filter(
      (e) => !EXCLUDED_EVENT_TYPES.has(e.event_type),
    );
    // Store keeps events chronologically (oldest at start).
    // Display newest at top.
    return [...filtered].reverse();
  }, [filteredEvents]);

  // Track which events are "new" for animation
  const newEventIds = useMemo(() => {
    const currentIds = new Set(displayEvents.map((e) => e.db_id));
    const newIds = new Set<number>();
    for (const id of currentIds) {
      if (!prevEventIdsRef.current.has(id)) {
        newIds.add(id);
      }
    }
    // Update the ref for next render (only after initial load)
    if (initialLoaded) {
      prevEventIdsRef.current = currentIds;
    }
    return newIds;
  }, [displayEvents, initialLoaded]);

  // ── Render ─────────────────────────────────────────────────────────

  return (
    <PageWrapper>
      {/* ── Header ────────────────────────────────────────────── */}
      <PageHeader>
        <PageTitle>{t("activity.title")}</PageTitle>
        <FilterBar>
          {/* Category filter — segmented buttons */}
          <FilterGroup>
            <FilterLabel>{t("activity.filterCategoryLabel")}</FilterLabel>
            <CategoryButtons>
              {CATEGORY_OPTIONS.map((opt) => (
                <CategoryButton
                  key={opt.value}
                  $active={
                    opt.value === "all"
                      ? filterCategory === null
                      : filterCategory === opt.value
                  }
                  onClick={() =>
                    handleCategoryChange(opt.value as EventCategory | "all")
                  }
                >
                  {t(opt.labelKey)}
                </CategoryButton>
              ))}
            </CategoryButtons>
          </FilterGroup>

          {/* Layer filter — dropdown */}
          <FilterGroup>
            <FilterLabel>{t("activity.filterLayerLabel")}</FilterLabel>
            <Select
              $size="sm"
              value={filterLayer ?? "all"}
              onChange={handleLayerChange}
            >
              <option value="all">{t("activity.allLayers")}</option>
              {layers.map((layer) => (
                <option key={layer.slug} value={layer.slug}>
                  {layer.display_name}
                </option>
              ))}
            </Select>
          </FilterGroup>
        </FilterBar>
      </PageHeader>

      {/* ── Event list ────────────────────────────────────────── */}
      {loading && !initialLoaded ? (
        <LoadingState message={t("activity.loadingHistory")} />
      ) : error ? (
        <ErrorState
          message={t("activity.loadError")}
          onRetry={handleRetry}
        />
      ) : displayEvents.length === 0 ? (
        <EmptyState
          title={t("activity.noActivity")}
          subtitle={t("activity.noActivityDescription")}
          icon="\uD83D\uDCCA"
        />
      ) : (
        <EventList>
          {displayEvents.map((event: ActivityEvent) => (
            <EventItem
              key={event.db_id}
              event={event}
              isNew={newEventIds.has(event.db_id)}
            />
          ))}

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
                  ? t("activity.loadingMore")
                  : t("activity.loadMore")}
              </Button>
            </LoadMoreWrapper>
          )}
        </EventList>
      )}
    </PageWrapper>
  );
}
