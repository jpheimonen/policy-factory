/**
 * Styled components for the Ideas page.
 *
 * Layout: page wrapper, submission area, filter/sort controls bar,
 * idea list, idea card (summary + expanded detail), radar chart area,
 * critic sections, synthesis section, action buttons.
 */
import styled, { css, keyframes } from "styled-components";

// ── Page layout ──────────────────────────────────────────────────────

export const PageWrapper = styled.div`
  max-width: 860px;
  margin: 0 auto;
  padding: ${({ theme }) => theme.spacing.xl};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.xl};
`;

export const PageHeader = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.sm};
`;

export const PageTitleRow = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing.md};
  flex-wrap: wrap;
`;

export const StatsBadges = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing.sm};
  flex-wrap: wrap;
`;

// ── Submission area ──────────────────────────────────────────────────

export const SubmissionArea = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.md};
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.lg};
  padding: ${({ theme }) => theme.spacing.lg};
`;

export const SubmissionRow = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing.sm};
  align-items: flex-end;

  @media (max-width: 768px) {
    flex-direction: column;
    align-items: stretch;
  }
`;

export const SubmissionActions = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing.sm};
  align-items: center;
  flex-shrink: 0;
`;

export const ErrorMessage = styled.div`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.status.error.text};
  background: ${({ theme }) => theme.colors.status.error.bg};
  border: 1px solid ${({ theme }) => theme.colors.status.error.border};
  border-radius: ${({ theme }) => theme.radii.md};
  padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
`;

// ── Controls bar ─────────────────────────────────────────────────────

export const ControlsBar = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing.md};
  align-items: center;
  flex-wrap: wrap;
`;

export const ControlGroup = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing.xs};
  align-items: center;
`;

export const ControlLabel = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.muted};
  white-space: nowrap;
`;

// ── Idea list ────────────────────────────────────────────────────────

export const IdeaList = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.sm};
`;

// ── Idea card ────────────────────────────────────────────────────────

export const IdeaCard = styled.div<{ $expanded?: boolean }>`
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.lg};
  overflow: hidden;
  transition:
    border-color ${({ theme }) => theme.transitions.normal},
    box-shadow ${({ theme }) => theme.transitions.normal};

  ${({ $expanded, theme }) =>
    $expanded &&
    css`
      border-color: ${theme.colors.accent.blue};
      box-shadow: ${theme.shadows.sm};
    `}
`;

export const IdeaCardSummary = styled.div`
  padding: ${({ theme }) => theme.spacing.lg};
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.sm};

  &:hover {
    background: ${({ theme }) => theme.colors.bg.tertiary};
  }
`;

export const IdeaTextPreview = styled.div`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.md};
  color: ${({ theme }) => theme.colors.text.primary};
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
`;

export const IdeaMeta = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing.sm};
  align-items: center;
  flex-wrap: wrap;
`;

export const IdeaMetaItem = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.text.muted};
`;

export const IdeaScoreBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.accent.blue};
  background: ${({ theme }) => theme.colors.status.active.bg};
  border-radius: ${({ theme }) => theme.radii.xl};
  padding: 2px 8px;
`;

// ── Expanded detail ──────────────────────────────────────────────────

export const ExpandedDetail = styled.div`
  border-top: 1px solid ${({ theme }) => theme.colors.border.default};
  padding: ${({ theme }) => theme.spacing.lg};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.lg};
`;

export const FullIdeaText = styled.div`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.md};
  color: ${({ theme }) => theme.colors.text.primary};
  line-height: 1.6;
  white-space: pre-wrap;
`;

export const ScoreSection = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.md};
  align-items: center;
`;

export const ScoreGrid = styled.div`
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: ${({ theme }) => theme.spacing.sm};
  width: 100%;
  max-width: 420px;

  @media (max-width: 768px) {
    grid-template-columns: repeat(2, 1fr);
  }
`;

export const ScoreItem = styled.div`
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: ${({ theme }) => theme.spacing.sm};
  background: ${({ theme }) => theme.colors.bg.tertiary};
  border-radius: ${({ theme }) => theme.radii.md};
  text-align: center;
`;

export const ScoreLabel = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.text.muted};
`;

export const ScoreValue = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.base};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text.primary};
`;

export const OverallScoreDisplay = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
  padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
  background: ${({ theme }) => theme.colors.status.active.bg};
  border: 1px solid ${({ theme }) => theme.colors.status.active.border};
  border-radius: ${({ theme }) => theme.radii.lg};
`;

export const OverallScoreLabel = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.secondary};
`;

export const OverallScoreValue = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.lg};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.accent.blue};
`;

// ── Critic sections ──────────────────────────────────────────────────

export const CriticSection = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.sm};
`;

export const CriticHeader = styled.button`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
  padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
  background: ${({ theme }) => theme.colors.bg.tertiary};
  border: 1px solid ${({ theme }) => theme.colors.border.subtle};
  border-radius: ${({ theme }) => theme.radii.md};
  cursor: pointer;
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.md};
  font-weight: 500;
  color: ${({ theme }) => theme.colors.text.primary};
  width: 100%;
  text-align: left;
  transition: background ${({ theme }) => theme.transitions.fast};

  &:hover {
    background: ${({ theme }) => theme.colors.bg.elevated};
  }
`;

export const CriticChevron = styled.span<{ $open: boolean }>`
  display: inline-flex;
  transition: transform ${({ theme }) => theme.transitions.fast};
  transform: rotate(${({ $open }) => ($open ? "90deg" : "0deg")});
  font-size: 12px;
  color: ${({ theme }) => theme.colors.text.muted};
`;

export const CriticBody = styled.div`
  padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
  padding-left: ${({ theme }) => theme.spacing.xl};
`;

// ── Synthesis section ────────────────────────────────────────────────

export const SynthesisSection = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.sm};
  padding: ${({ theme }) => theme.spacing.md};
  background: ${({ theme }) => theme.colors.bg.tertiary};
  border-radius: ${({ theme }) => theme.radii.lg};
  border: 1px solid ${({ theme }) => theme.colors.border.subtle};
`;

export const TensionPoint = styled.div`
  padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
  background: ${({ theme }) => theme.colors.status.warning.bg};
  border-left: 3px solid ${({ theme }) => theme.colors.status.warning.text};
  border-radius: ${({ theme }) => theme.radii.sm};
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.primary};
  line-height: 1.5;
`;

// ── Detail actions ───────────────────────────────────────────────────

export const DetailActions = styled.div`
  display: flex;
  gap: ${({ theme }) => theme.spacing.sm};
  padding-top: ${({ theme }) => theme.spacing.sm};
  border-top: 1px solid ${({ theme }) => theme.colors.border.subtle};
`;

// ── Placeholder ──────────────────────────────────────────────────────

export const PlaceholderText = styled.div`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.muted};
  font-style: italic;
  text-align: center;
  padding: ${({ theme }) => theme.spacing.md};
`;

// ── Section heading ──────────────────────────────────────────────────

export const SectionHeading = styled.h3`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.md};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text.primary};
  margin: 0;
`;

// ── Dot separator ────────────────────────────────────────────────────

export const DotSeparator = styled.span`
  color: ${({ theme }) => theme.colors.text.muted};
  font-size: ${({ theme }) => theme.fontSizes.xs};

  &::before {
    content: "\u00b7";
  }
`;

// ── Loading skeleton ─────────────────────────────────────────────────

const shimmer = keyframes`
  0% { background-position: -200px 0; }
  100% { background-position: calc(200px + 100%) 0; }
`;

export const SkeletonCard = styled.div`
  height: 100px;
  background: linear-gradient(
    90deg,
    ${({ theme }) => theme.colors.bg.secondary} 25%,
    ${({ theme }) => theme.colors.bg.tertiary} 37%,
    ${({ theme }) => theme.colors.bg.secondary} 63%
  );
  background-size: 400px 100%;
  animation: ${shimmer} 1.4s ease infinite;
  border-radius: ${({ theme }) => theme.radii.lg};
  border: 1px solid ${({ theme }) => theme.colors.border.subtle};
`;

// ── Load more ────────────────────────────────────────────────────────

export const LoadMoreWrapper = styled.div`
  display: flex;
  justify-content: center;
  padding: ${({ theme }) => theme.spacing.md};
`;
