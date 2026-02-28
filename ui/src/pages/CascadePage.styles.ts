/**
 * Styled components for the Live Cascade Viewer page.
 *
 * Follows the cc-runner pattern of co-located .styles.ts files with
 * transient $ props, theme token usage, and keyframe animations.
 *
 * The page adapts visually based on cascade state:
 * - Running: active/animated with streaming text and progress
 * - Paused: warning-toned with error display
 * - Idle: neutral with history section
 */
import styled, { css, keyframes } from "styled-components";
import type { Theme } from "@/styles/theme.ts";

// ── Layer color helper ───────────────────────────────────────────────

type LayerSlug =
  | "values"
  | "situational-awareness"
  | "strategic-objectives"
  | "tactical-objectives"
  | "policies";

export function getLayerColors(theme: Theme, slug: string) {
  const key = slug as LayerSlug;
  return theme.colors.layers[key] ?? theme.colors.layers.values;
}

// ── Keyframe animations ──────────────────────────────────────────────

export const cursorBlink = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
`;

const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
`;

const spin = keyframes`
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
`;

// ── Page layout ──────────────────────────────────────────────────────

export const PageWrapper = styled.div`
  max-width: 960px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.xl};
`;

// ── Page header ──────────────────────────────────────────────────────

export const PageHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing.md};
  flex-wrap: wrap;
`;

export const HeaderLeft = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.md};
`;

export const HeaderRight = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
`;

export const HeaderMeta = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.md};
  color: ${({ theme }) => theme.colors.text.secondary};
  font-size: ${({ theme }) => theme.fontSizes.sm};
`;

// ── Progress indicator ───────────────────────────────────────────────

export const ProgressContainer = styled.div`
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.lg};
  overflow: hidden;
`;

export const CompactProgress = styled.div`
  display: none;
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};

  @media (max-width: 640px) {
    display: block;
  }
`;

export const CompactProgressText = styled.div`
  color: ${({ theme }) => theme.colors.text.primary};
  font-size: ${({ theme }) => theme.fontSizes.md};
  font-weight: 500;
  margin-bottom: ${({ theme }) => theme.spacing.sm};
`;

export const CompactProgressBar = styled.div`
  height: 4px;
  background: ${({ theme }) => theme.colors.bg.tertiary};
  border-radius: 2px;
  overflow: hidden;
`;

export const CompactProgressFill = styled.div<{ $percent: number; $color: string }>`
  height: 100%;
  width: ${({ $percent }) => $percent}%;
  background: ${({ $color }) => $color};
  border-radius: 2px;
  transition: width ${({ theme }) => theme.transitions.normal};
`;

export const DesktopProgress = styled.div`
  display: flex;
  align-items: stretch;
  gap: 0;
  width: 100%;
  padding: ${({ theme }) => theme.spacing.md};

  @media (max-width: 640px) {
    display: none;
  }
`;

export const ProgressLayerGroup = styled.div<{
  $state: "completed" | "active" | "upcoming" | "failed";
  $layerSlug: string;
}>`
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.xs};
  padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.xs};
  border-radius: ${({ theme }) => theme.radii.md};
  transition: background ${({ theme }) => theme.transitions.normal};
  min-width: 0;

  ${({ $state, theme, $layerSlug }) => {
    switch ($state) {
      case "completed":
        return css`
          opacity: 0.65;
        `;
      case "active":
        return css`
          background: ${getLayerColors(theme, $layerSlug).bg};
        `;
      case "failed":
        return css`
          background: ${theme.colors.status.error.bg};
        `;
      case "upcoming":
        return css`
          opacity: 0.35;
        `;
    }
  }}
`;

export const ProgressLayerName = styled.div<{ $layerSlug: string }>`
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: 600;
  color: ${({ theme, $layerSlug }) => getLayerColors(theme, $layerSlug).text};
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
  text-align: center;
`;

export const ProgressSteps = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
`;

export const ProgressStepDot = styled.div<{
  $state: "done" | "active" | "pending" | "failed";
  $layerSlug: string;
}>`
  width: 8px;
  height: 8px;
  border-radius: 50%;
  transition: all ${({ theme }) => theme.transitions.fast};

  ${({ $state, theme, $layerSlug }) => {
    switch ($state) {
      case "done":
        return css`
          background: ${getLayerColors(theme, $layerSlug).primary};
        `;
      case "active":
        return css`
          background: ${getLayerColors(theme, $layerSlug).primary};
          animation: ${pulse} 1.5s ease-in-out infinite;
          box-shadow: 0 0 6px ${getLayerColors(theme, $layerSlug).primary}88;
        `;
      case "failed":
        return css`
          background: ${theme.colors.status.error.text};
        `;
      case "pending":
        return css`
          background: ${theme.colors.bg.tertiary};
          border: 1px solid ${theme.colors.border.default};
        `;
    }
  }}
`;

export const ProgressStepLabel = styled.span`
  font-size: 10px;
  color: ${({ theme }) => theme.colors.text.muted};
  white-space: nowrap;
`;

export const ProgressArrow = styled.div`
  color: ${({ theme }) => theme.colors.text.muted};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  padding: 0 2px;
  flex-shrink: 0;
  display: flex;
  align-items: center;

  @media (max-width: 640px) {
    display: none;
  }
`;

// ── Active agent label ───────────────────────────────────────────────

export const AgentLabel = styled.div<{ $layerSlug?: string }>`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-left: 3px solid
    ${({ theme, $layerSlug }) =>
      $layerSlug
        ? getLayerColors(theme, $layerSlug).primary
        : theme.colors.accent.blue};
  border-radius: ${({ theme }) => theme.radii.md};
  font-size: ${({ theme }) => theme.fontSizes.md};
  font-weight: 500;
  color: ${({ theme }) => theme.colors.text.primary};
`;

export const AgentSpinner = styled.div`
  width: 14px;
  height: 14px;
  border: 2px solid ${({ theme }) => theme.colors.text.muted};
  border-right-color: transparent;
  border-radius: 50%;
  animation: ${spin} 0.6s linear infinite;
  flex-shrink: 0;
`;

// ── Streaming text panel ─────────────────────────────────────────────

export const StreamingContainer = styled.div`
  position: relative;
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.lg};
  overflow: hidden;
`;

export const StreamingScroller = styled.div`
  height: 420px;
  overflow-y: auto;
  padding: ${({ theme }) => theme.spacing.lg};

  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-track {
    background: transparent;
  }
  &::-webkit-scrollbar-thumb {
    background: ${({ theme }) => theme.colors.border.default};
    border-radius: 3px;
  }
`;

export const StreamingText = styled.pre`
  font-family: ${({ theme }) => theme.fonts.mono};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  line-height: 1.6;
  color: ${({ theme }) => theme.colors.text.primary};
  white-space: pre-wrap;
  word-wrap: break-word;
  margin: 0;
`;

export const StreamingCursor = styled.span`
  display: inline-block;
  width: 8px;
  height: 16px;
  background: ${({ theme }) => theme.colors.accent.blue};
  margin-left: 2px;
  vertical-align: text-bottom;
  animation: ${cursorBlink} 1s step-end infinite;
`;

export const StreamingEmpty = styled.div`
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  min-height: 120px;
  color: ${({ theme }) => theme.colors.text.muted};
  font-size: ${({ theme }) => theme.fontSizes.md};
  gap: ${({ theme }) => theme.spacing.sm};
`;

export const StreamingEmptySpinner = styled.div`
  width: 16px;
  height: 16px;
  border: 2px solid ${({ theme }) => theme.colors.text.muted};
  border-right-color: transparent;
  border-radius: 50%;
  animation: ${spin} 0.8s linear infinite;
`;

// ── Error display ────────────────────────────────────────────────────

export const ErrorCard = styled.div`
  padding: ${({ theme }) => theme.spacing.lg} ${({ theme }) => theme.spacing.xl};
  background: ${({ theme }) => theme.colors.status.error.bg};
  border: 1px solid ${({ theme }) => theme.colors.status.error.border};
  border-radius: ${({ theme }) => theme.radii.lg};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.md};
`;

export const ErrorTitle = styled.div`
  font-weight: 600;
  color: ${({ theme }) => theme.colors.status.error.text};
  font-size: ${({ theme }) => theme.fontSizes.md};
`;

export const ErrorDetail = styled.div`
  color: ${({ theme }) => theme.colors.text.secondary};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  line-height: 1.5;
`;

export const ErrorActions = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
  margin-top: ${({ theme }) => theme.spacing.xs};
`;

// ── Queue section ────────────────────────────────────────────────────

export const QueueSection = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.md};
`;

export const QueueEntry = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing.md};
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.md};
`;

export const QueueEntryInfo = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
`;

export const QueueEntryTitle = styled.div`
  font-size: ${({ theme }) => theme.fontSizes.md};
  color: ${({ theme }) => theme.colors.text.primary};
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
`;

export const QueueEntryMeta = styled.div`
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.text.muted};
`;

// ── History section ──────────────────────────────────────────────────

export const HistorySection = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.md};
`;

export const SectionHeading = styled.h2`
  font-size: ${({ theme }) => theme.fontSizes.lg};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text.primary};
  margin: 0;
`;

export const HistoryEntry = styled.div`
  display: flex;
  flex-direction: column;
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.md};
  overflow: hidden;
  cursor: pointer;
  transition: border-color ${({ theme }) => theme.transitions.fast};

  &:hover {
    border-color: ${({ theme }) => theme.colors.text.muted};
  }
`;

export const HistoryEntryHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing.md};
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
`;

export const HistoryEntryLeft = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.md};
  min-width: 0;
`;

export const HistoryEntryRight = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
  flex-shrink: 0;
`;

export const HistoryEntryMeta = styled.div`
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.text.muted};
`;

export const HistoryDetail = styled.div`
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
  border-top: 1px solid ${({ theme }) => theme.colors.border.subtle};
  background: ${({ theme }) => theme.colors.bg.tertiary};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.secondary};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.sm};
`;

// ── Idle state ───────────────────────────────────────────────────────

export const IdleContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 200px;
  gap: ${({ theme }) => theme.spacing.lg};
  padding: ${({ theme }) => theme.spacing.xxl};
  text-align: center;
`;

// ── Layer badge ──────────────────────────────────────────────────────

export const LayerBadge = styled.span<{ $layerSlug: string }>`
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: 500;
  line-height: 1.4;
  border-radius: ${({ theme }) => theme.radii.xl};
  white-space: nowrap;
  background: ${({ theme, $layerSlug }) => getLayerColors(theme, $layerSlug).bg};
  color: ${({ theme, $layerSlug }) => getLayerColors(theme, $layerSlug).text};
  border: 1px solid ${({ theme, $layerSlug }) => getLayerColors(theme, $layerSlug).primary}33;
`;
