/**
 * IdeaRadarChart molecule.
 *
 * Renders a 6-axis radar chart for idea evaluation scores using recharts.
 * Follows the cc-runner pattern: ResponsiveContainer, useTheme() for
 * theme-aware colours, styled-components co-location.
 *
 * Reusable — can display any 6-axis score set (idea evaluations, etc.).
 */
import { memo } from "react";
import {
  RadarChart,
  Radar,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { useTheme } from "styled-components";
import styled from "styled-components";
import { useTranslation } from "@/i18n/index.ts";
import type { IdeaScores } from "@/stores/ideaStore.ts";

// ── Types ────────────────────────────────────────────────────────────

interface IdeaRadarChartProps {
  /** The 6-axis scores to display. */
  scores: IdeaScores;
  /** Optional size override (default 280px). */
  size?: number;
}

// ── Score axis configuration ─────────────────────────────────────────

const SCORE_AXES = [
  { key: "strategic_fit", labelKey: "ideas.scoreStrategicFit" },
  { key: "feasibility", labelKey: "ideas.scoreFeasibility" },
  { key: "cost", labelKey: "ideas.scoreCost" },
  { key: "risk", labelKey: "ideas.scoreRisk" },
  { key: "public_acceptance", labelKey: "ideas.scorePublicAcceptance" },
  { key: "international_impact", labelKey: "ideas.scoreInternationalImpact" },
] as const;

// ── Styled wrappers ──────────────────────────────────────────────────

const ChartWrapper = styled.div<{ $size: number }>`
  width: ${({ $size }) => $size}px;
  height: ${({ $size }) => $size}px;
  margin: 0 auto;
`;

// ── Component ────────────────────────────────────────────────────────

export const IdeaRadarChart = memo(function IdeaRadarChart({
  scores,
  size = 280,
}: IdeaRadarChartProps) {
  const theme = useTheme();
  const { t } = useTranslation();

  // Transform scores into recharts data format
  const data = SCORE_AXES.map((axis) => ({
    axis: t(axis.labelKey),
    value: scores[axis.key as keyof IdeaScores] ?? 0,
    fullMark: 10,
  }));

  return (
    <ChartWrapper $size={size}>
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
          <PolarGrid
            stroke={theme.colors.border.default}
            strokeDasharray="3 3"
          />
          <PolarAngleAxis
            dataKey="axis"
            tick={{
              fill: theme.colors.text.secondary,
              fontSize: 11,
            }}
          />
          <PolarRadiusAxis
            angle={90}
            domain={[0, 10]}
            tick={{
              fill: theme.colors.text.muted,
              fontSize: 10,
            }}
            tickCount={6}
            axisLine={false}
          />
          <Radar
            name="Score"
            dataKey="value"
            stroke={theme.colors.accent.blue}
            fill={theme.colors.accent.blue}
            fillOpacity={0.2}
            strokeWidth={2}
          />
          <Tooltip
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null;
              const item = payload[0].payload as {
                axis: string;
                value: number;
              };
              return (
                <div
                  style={{
                    backgroundColor: theme.colors.bg.elevated,
                    border: `1px solid ${theme.colors.border.default}`,
                    borderRadius: theme.radii.md,
                    padding: "6px 10px",
                    fontSize: 12,
                    fontFamily: theme.fonts.sans,
                  }}
                >
                  <div
                    style={{
                      fontWeight: 500,
                      color: theme.colors.text.primary,
                    }}
                  >
                    {item.axis}
                  </div>
                  <div style={{ color: theme.colors.text.secondary }}>
                    {item.value.toFixed(1)} / 10
                  </div>
                </div>
              );
            }}
          />
        </RadarChart>
      </ResponsiveContainer>
    </ChartWrapper>
  );
});
