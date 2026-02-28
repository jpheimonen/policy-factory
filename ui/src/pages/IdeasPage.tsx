/**
 * Ideas page — the idea inbox.
 *
 * Route: /ideas
 *
 * Features:
 * - Idea submission form with optimistic UI
 * - AI idea generation trigger
 * - Filterable, sortable idea list
 * - Expandable idea detail with radar chart, critic assessments, synthesis
 * - Pagination (load more)
 * - Real-time updates via WebSocket events
 *
 * Step 021: replaces the placeholder from step 009.
 */
import { useEffect, useState, useCallback, useMemo } from "react";
import { useTranslation } from "@/i18n/index.ts";
import { useIdeaStore } from "@/stores/ideaStore.ts";
import { useLayerStore } from "@/stores/layerStore.ts";
import { CRITIC_ORDER, CRITIC_DISPLAY_KEYS } from "@/stores/ideaStore.ts";
import type {
  IdeaSummary,
  IdeaDetail,
  IdeaFilterStatus,
  IdeaSortField,
  IdeaSortOrder,
} from "@/stores/ideaStore.ts";
import { formatRelativeTime } from "@/lib/timeUtils.ts";
import { Text, Badge, Button, Textarea, Select, Markdown } from "@/components/atoms/index.ts";
import { LoadingState } from "@/components/molecules/LoadingState.tsx";
import { ErrorState } from "@/components/molecules/ErrorState.tsx";
import { EmptyState } from "@/components/molecules/EmptyState.tsx";
import { IdeaRadarChart } from "@/components/molecules/IdeaRadarChart.tsx";
import type { BadgeVariant } from "@/components/atoms/Badge.ts";
import * as S from "./IdeasPage.styles.ts";

// ── Helpers ──────────────────────────────────────────────────────────

/** Map idea status to badge variant. */
function statusToVariant(status: string): BadgeVariant {
  switch (status) {
    case "pending":
      return "info";
    case "evaluating":
      return "warning";
    case "evaluated":
      return "success";
    case "archived":
      return "neutral";
    default:
      return "neutral";
  }
}

/** Map sort dropdown value to field + order. */
function parseSortValue(value: string): {
  field: IdeaSortField;
  order: IdeaSortOrder;
} {
  switch (value) {
    case "newest":
      return { field: "submission_date", order: "desc" };
    case "oldest":
      return { field: "submission_date", order: "asc" };
    case "highest_score":
      return { field: "score", order: "desc" };
    case "lowest_score":
      return { field: "score", order: "asc" };
    default:
      return { field: "submission_date", order: "desc" };
  }
}

/** Convert current sort state to dropdown value. */
function sortToValue(field: IdeaSortField, order: IdeaSortOrder): string {
  if (field === "submission_date" && order === "desc") return "newest";
  if (field === "submission_date" && order === "asc") return "oldest";
  if (field === "score" && order === "desc") return "highest_score";
  if (field === "score" && order === "asc") return "lowest_score";
  return "newest";
}

// ── Main component ───────────────────────────────────────────────────

export function IdeasPage() {
  const { t } = useTranslation();
  const {
    ideas,
    expandedId,
    expandedDetail,
    filterStatus,
    sortField,
    sortOrder,
    loading,
    detailLoading,
    submitting,
    generating,
    archiving,
    reEvaluating,
    error,
    detailError,
    submitError,
    hasMore,
    loadingMore,
    fetchIdeas,
    loadMore,
    submitIdea,
    triggerGeneration,
    archiveIdea,
    reEvaluateIdea,
    setFilter,
    setSort,
    expandIdea,
    collapseIdea,
  } = useIdeaStore();

  // Layer store for scoping selector
  const { layers, init: initLayers } = useLayerStore();

  // Local form state
  const [ideaText, setIdeaText] = useState("");

  // Fetch ideas on mount
  useEffect(() => {
    fetchIdeas();
    initLayers();
  }, [fetchIdeas, initLayers]);

  // ── Summary statistics ───────────────────────────────────────────

  const stats = useMemo(() => {
    const total = ideas.length;
    const pending = ideas.filter((i) => i.status === "pending").length;
    const evaluating = ideas.filter((i) => i.status === "evaluating").length;
    const evaluated = ideas.filter((i) => i.status === "evaluated").length;
    return { total, pending, evaluating, evaluated };
  }, [ideas]);

  // ── Handlers ─────────────────────────────────────────────────────

  const handleSubmit = useCallback(async () => {
    if (!ideaText.trim()) return;
    await submitIdea(ideaText.trim());
    setIdeaText("");
  }, [ideaText, submitIdea]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  const handleGenerate = useCallback(() => {
    triggerGeneration();
  }, [triggerGeneration]);

  const handleFilterChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      setFilter(e.target.value as IdeaFilterStatus);
    },
    [setFilter],
  );

  const handleSortChange = useCallback(
    (e: React.ChangeEvent<HTMLSelectElement>) => {
      const { field, order } = parseSortValue(e.target.value);
      setSort(field, order);
    },
    [setSort],
  );

  // Suppress unused variable warnings for layers — used for future scoping
  void layers;

  // ── Render ───────────────────────────────────────────────────────

  return (
    <S.PageWrapper>
      {/* Page header */}
      <S.PageHeader>
        <S.PageTitleRow>
          <Text as="h1" $variant="heading" $size="xl">
            {t("ideas.title")}
          </Text>
          <S.StatsBadges>
            <Badge $variant="neutral">
              {t("ideas.summaryTotal", { count: String(stats.total) })}
            </Badge>
            {stats.pending > 0 && (
              <Badge $variant="info">
                {t("ideas.summaryPending", { count: String(stats.pending) })}
              </Badge>
            )}
            {stats.evaluating > 0 && (
              <Badge $variant="warning">
                {t("ideas.summaryEvaluating", {
                  count: String(stats.evaluating),
                })}
              </Badge>
            )}
            {stats.evaluated > 0 && (
              <Badge $variant="success">
                {t("ideas.summaryEvaluated", {
                  count: String(stats.evaluated),
                })}
              </Badge>
            )}
          </S.StatsBadges>
        </S.PageTitleRow>
      </S.PageHeader>

      {/* Submission area */}
      <S.SubmissionArea>
        <Textarea
          value={ideaText}
          onChange={(e) => setIdeaText(e.target.value)}
          placeholder={t("ideas.submitPlaceholder")}
          onKeyDown={handleKeyDown}
          disabled={submitting}
          rows={3}
        />
        <S.SubmissionRow>
          <S.SubmissionActions>
            <Button
              $variant="primary"
              onClick={handleSubmit}
              disabled={!ideaText.trim() || submitting}
              $loading={submitting}
            >
              {submitting ? t("ideas.submitting") : t("ideas.submitButton")}
            </Button>
            <Button
              $variant="secondary"
              onClick={handleGenerate}
              disabled={generating}
              $loading={generating}
            >
              {generating
                ? t("ideas.generating")
                : t("ideas.generateButton")}
            </Button>
          </S.SubmissionActions>
        </S.SubmissionRow>
        {submitError && <S.ErrorMessage>{submitError}</S.ErrorMessage>}
      </S.SubmissionArea>

      {/* Filter and sort controls */}
      <S.ControlsBar>
        <S.ControlGroup>
          <S.ControlLabel>{t("ideas.filterByStatus")}</S.ControlLabel>
          <Select
            $size="sm"
            value={filterStatus}
            onChange={handleFilterChange}
          >
            <option value="all">{t("ideas.filterAll")}</option>
            <option value="pending">{t("ideas.filterPending")}</option>
            <option value="evaluating">{t("ideas.filterEvaluating")}</option>
            <option value="evaluated">{t("ideas.filterEvaluated")}</option>
            <option value="archived">{t("ideas.filterArchived")}</option>
          </Select>
        </S.ControlGroup>

        <S.ControlGroup>
          <S.ControlLabel>{t("common.sort")}</S.ControlLabel>
          <Select
            $size="sm"
            value={sortToValue(sortField, sortOrder)}
            onChange={handleSortChange}
          >
            <option value="newest">{t("ideas.sortByRecent")}</option>
            <option value="oldest">{t("ideas.sortByOldest")}</option>
            <option value="highest_score">{t("ideas.sortByScore")}</option>
            <option value="lowest_score">{t("ideas.sortByScoreAsc")}</option>
          </Select>
        </S.ControlGroup>
      </S.ControlsBar>

      {/* Idea list */}
      {loading ? (
        <S.IdeaList>
          <S.SkeletonCard />
          <S.SkeletonCard />
          <S.SkeletonCard />
        </S.IdeaList>
      ) : error ? (
        <ErrorState message={error} onRetry={fetchIdeas} />
      ) : ideas.length === 0 ? (
        <EmptyState
          icon="\ud83d\udca1"
          title={t("ideas.noIdeas")}
          subtitle={t("ideas.noIdeasDescription")}
        />
      ) : (
        <>
          <S.IdeaList>
            {ideas.map((idea) => (
              <IdeaCardItem
                key={idea.id}
                idea={idea}
                isExpanded={expandedId === idea.id}
                detail={expandedId === idea.id ? expandedDetail : null}
                detailLoading={expandedId === idea.id && detailLoading}
                detailError={expandedId === idea.id ? detailError : null}
                archiving={archiving === idea.id}
                reEvaluating={reEvaluating === idea.id}
                onToggle={() => expandIdea(idea.id)}
                onCollapse={collapseIdea}
                onArchive={() => archiveIdea(idea.id)}
                onReEvaluate={() => reEvaluateIdea(idea.id)}
              />
            ))}
          </S.IdeaList>

          {/* Load more */}
          {hasMore && (
            <S.LoadMoreWrapper>
              <Button
                $variant="secondary"
                onClick={loadMore}
                disabled={loadingMore}
                $loading={loadingMore}
              >
                {loadingMore ? t("ideas.loadingMore") : t("ideas.loadMore")}
              </Button>
            </S.LoadMoreWrapper>
          )}
        </>
      )}
    </S.PageWrapper>
  );
}

// ── Idea card sub-component ──────────────────────────────────────────

interface IdeaCardItemProps {
  idea: IdeaSummary;
  isExpanded: boolean;
  detail: IdeaDetail | null;
  detailLoading: boolean;
  detailError: string | null;
  archiving: boolean;
  reEvaluating: boolean;
  onToggle: () => void;
  onCollapse: () => void;
  onArchive: () => void;
  onReEvaluate: () => void;
}

function IdeaCardItem({
  idea,
  isExpanded,
  detail,
  detailLoading,
  detailError,
  archiving,
  reEvaluating,
  onToggle,
  onCollapse,
  onArchive,
  onReEvaluate,
}: IdeaCardItemProps) {
  const { t } = useTranslation();

  // Status label
  const statusLabel =
    idea.status === "pending"
      ? t("ideas.statusPending")
      : idea.status === "evaluating"
        ? t("ideas.statusEvaluating")
        : idea.status === "evaluated"
          ? t("ideas.statusEvaluated")
          : t("ideas.statusArchived");

  // Source label
  const sourceLabel =
    idea.source === "human" ? t("ideas.sourceHuman") : t("ideas.sourceAI");

  return (
    <S.IdeaCard $expanded={isExpanded}>
      {/* Summary (always visible) */}
      <S.IdeaCardSummary onClick={onToggle}>
        <S.IdeaTextPreview>{idea.text || "\u2026"}</S.IdeaTextPreview>
        <S.IdeaMeta>
          <Badge $variant={statusToVariant(idea.status)}>{statusLabel}</Badge>
          <Badge
            $variant={idea.source === "human" ? "neutral" : "info"}
          >
            {sourceLabel}
          </Badge>
          {idea.overall_score !== null && (
            <S.IdeaScoreBadge>
              {t("ideas.overallScore")}: {idea.overall_score.toFixed(1)}
            </S.IdeaScoreBadge>
          )}
          <S.DotSeparator />
          <S.IdeaMetaItem>
            {t("ideas.submittedBy", { user: idea.submitted_by || "Unknown" })}
          </S.IdeaMetaItem>
          <S.DotSeparator />
          <S.IdeaMetaItem>
            {formatRelativeTime(idea.submitted_at)}
          </S.IdeaMetaItem>
          {idea.target_objective && (
            <>
              <S.DotSeparator />
              <S.IdeaMetaItem>
                {t("ideas.targetObjective", {
                  objective: idea.target_objective,
                })}
              </S.IdeaMetaItem>
            </>
          )}
        </S.IdeaMeta>
      </S.IdeaCardSummary>

      {/* Expanded detail */}
      {isExpanded && (
        <S.ExpandedDetail>
          {detailLoading ? (
            <LoadingState compact />
          ) : detailError ? (
            <ErrorState message={detailError} compact />
          ) : detail ? (
            <IdeaDetailView
              detail={detail}
              archiving={archiving}
              reEvaluating={reEvaluating}
              onArchive={onArchive}
              onReEvaluate={onReEvaluate}
              onCollapse={onCollapse}
            />
          ) : null}
        </S.ExpandedDetail>
      )}
    </S.IdeaCard>
  );
}

// ── Idea detail view sub-component ───────────────────────────────────

interface IdeaDetailViewProps {
  detail: IdeaDetail;
  archiving: boolean;
  reEvaluating: boolean;
  onArchive: () => void;
  onReEvaluate: () => void;
  onCollapse: () => void;
}

function IdeaDetailView({
  detail,
  archiving,
  reEvaluating,
  onArchive,
  onReEvaluate,
  onCollapse,
}: IdeaDetailViewProps) {
  const { t } = useTranslation();
  const [openCritics, setOpenCritics] = useState<Set<string>>(new Set());

  const toggleCritic = useCallback((archetype: string) => {
    setOpenCritics((prev) => {
      const next = new Set(prev);
      if (next.has(archetype)) {
        next.delete(archetype);
      } else {
        next.add(archetype);
      }
      return next;
    });
  }, []);

  const isEvaluated = detail.status === "evaluated" && detail.scores;

  return (
    <>
      {/* Full idea text */}
      <S.FullIdeaText>{detail.text}</S.FullIdeaText>

      {/* Score section */}
      <div>
        <S.SectionHeading>{t("ideas.radarTitle")}</S.SectionHeading>
        {isEvaluated && detail.scores ? (
          <S.ScoreSection>
            <IdeaRadarChart scores={detail.scores} />

            {/* Overall score */}
            <S.OverallScoreDisplay>
              <S.OverallScoreLabel>{t("ideas.overallScore")}</S.OverallScoreLabel>
              <S.OverallScoreValue>
                {detail.scores.overall_score.toFixed(1)}
              </S.OverallScoreValue>
            </S.OverallScoreDisplay>

            {/* Score grid */}
            <S.ScoreGrid>
              <S.ScoreItem>
                <S.ScoreLabel>{t("ideas.scoreStrategicFit")}</S.ScoreLabel>
                <S.ScoreValue>
                  {detail.scores.strategic_fit.toFixed(1)}
                </S.ScoreValue>
              </S.ScoreItem>
              <S.ScoreItem>
                <S.ScoreLabel>{t("ideas.scoreFeasibility")}</S.ScoreLabel>
                <S.ScoreValue>
                  {detail.scores.feasibility.toFixed(1)}
                </S.ScoreValue>
              </S.ScoreItem>
              <S.ScoreItem>
                <S.ScoreLabel>{t("ideas.scoreCost")}</S.ScoreLabel>
                <S.ScoreValue>{detail.scores.cost.toFixed(1)}</S.ScoreValue>
              </S.ScoreItem>
              <S.ScoreItem>
                <S.ScoreLabel>{t("ideas.scoreRisk")}</S.ScoreLabel>
                <S.ScoreValue>{detail.scores.risk.toFixed(1)}</S.ScoreValue>
              </S.ScoreItem>
              <S.ScoreItem>
                <S.ScoreLabel>{t("ideas.scorePublicAcceptance")}</S.ScoreLabel>
                <S.ScoreValue>
                  {detail.scores.public_acceptance.toFixed(1)}
                </S.ScoreValue>
              </S.ScoreItem>
              <S.ScoreItem>
                <S.ScoreLabel>
                  {t("ideas.scoreInternationalImpact")}
                </S.ScoreLabel>
                <S.ScoreValue>
                  {detail.scores.international_impact.toFixed(1)}
                </S.ScoreValue>
              </S.ScoreItem>
            </S.ScoreGrid>
          </S.ScoreSection>
        ) : (
          <S.PlaceholderText>{t("ideas.scoresNotAvailable")}</S.PlaceholderText>
        )}
      </div>

      {/* Critic assessments */}
      <div>
        <S.SectionHeading>{t("ideas.criticAssessments")}</S.SectionHeading>
        {detail.critic_assessments && detail.critic_assessments.length > 0 ? (
          <S.CriticSection>
            {CRITIC_ORDER.map((archetype) => {
              const assessment = detail.critic_assessments.find(
                (a) => a.archetype === archetype,
              );
              if (!assessment) return null;

              const displayKey = CRITIC_DISPLAY_KEYS[archetype];
              const isOpen = openCritics.has(archetype);

              return (
                <div key={archetype}>
                  <S.CriticHeader onClick={() => toggleCritic(archetype)}>
                    <S.CriticChevron $open={isOpen}>
                      {"\u25b6"}
                    </S.CriticChevron>
                    {displayKey ? t(displayKey) : archetype}
                  </S.CriticHeader>
                  {isOpen && (
                    <S.CriticBody>
                      <Markdown content={assessment.assessment_text} />
                    </S.CriticBody>
                  )}
                </div>
              );
            })}
          </S.CriticSection>
        ) : (
          <S.PlaceholderText>{t("ideas.criticNotAvailable")}</S.PlaceholderText>
        )}
      </div>

      {/* Synthesis */}
      <div>
        <S.SectionHeading>{t("ideas.synthesis")}</S.SectionHeading>
        {detail.synthesis ? (
          <S.SynthesisSection>
            <Markdown content={detail.synthesis.synthesis_text} />
            {detail.synthesis.structured_synthesis && (
              <StructuredSynthesis
                data={detail.synthesis.structured_synthesis}
              />
            )}
          </S.SynthesisSection>
        ) : (
          <S.PlaceholderText>
            {t("ideas.synthesisNotAvailable")}
          </S.PlaceholderText>
        )}
      </div>

      {/* Action buttons */}
      <S.DetailActions>
        {detail.status !== "archived" && (
          <Button
            $variant="ghost"
            $size="sm"
            onClick={onArchive}
            disabled={archiving}
            $loading={archiving}
          >
            {archiving ? t("ideas.archiving") : t("ideas.archiveButton")}
          </Button>
        )}
        {(detail.status === "pending" || detail.status === "evaluated") && (
          <Button
            $variant="secondary"
            $size="sm"
            onClick={onReEvaluate}
            disabled={reEvaluating}
            $loading={reEvaluating}
          >
            {reEvaluating
              ? t("ideas.reEvaluating")
              : t("ideas.reEvaluateButton")}
          </Button>
        )}
        <Button $variant="ghost" $size="sm" onClick={onCollapse}>
          {t("ideas.collapseButton")}
        </Button>
      </S.DetailActions>
    </>
  );
}

// ── Structured synthesis sub-component ───────────────────────────────

interface StructuredSynthesisProps {
  data: Record<string, unknown>;
}

function StructuredSynthesis({ data }: StructuredSynthesisProps) {
  const { t } = useTranslation();

  const consensus = data.consensus_points || data.consensus;
  const tensions = data.tension_points || data.tensions;
  const recommendations = data.recommendations;

  if (!consensus && !tensions && !recommendations) return null;

  return (
    <>
      {consensus && Array.isArray(consensus) && consensus.length > 0 && (
        <div>
          <S.SectionHeading>{t("ideas.synthesisConsensus")}</S.SectionHeading>
          {(consensus as string[]).map((point, i) => (
            <Text key={i} as="p" $variant="body" $size="sm">
              {point}
            </Text>
          ))}
        </div>
      )}

      {tensions && Array.isArray(tensions) && tensions.length > 0 && (
        <div>
          <S.SectionHeading>{t("ideas.synthesisTensions")}</S.SectionHeading>
          {(tensions as string[]).map((point, i) => (
            <S.TensionPoint key={i}>{point}</S.TensionPoint>
          ))}
        </div>
      )}

      {recommendations &&
        Array.isArray(recommendations) &&
        recommendations.length > 0 && (
          <div>
            <S.SectionHeading>
              {t("ideas.synthesisRecommendations")}
            </S.SectionHeading>
            {(recommendations as string[]).map((point, i) => (
              <Text key={i} as="p" $variant="body" $size="sm">
                {point}
              </Text>
            ))}
          </div>
        )}
    </>
  );
}
