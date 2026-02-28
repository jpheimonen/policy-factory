/**
 * Styled components for the Version History page.
 *
 * A vertical timeline of git commits for a specific layer.
 * Each commit entry has a timeline connector (vertical line on the left),
 * with the commit message as the most prominent text.
 */
import styled from "styled-components";
import type { Theme } from "@/styles/theme.ts";

// ── Layer color helper ───────────────────────────────────────────────

type LayerSlug =
  | "values"
  | "situational-awareness"
  | "strategic-objectives"
  | "tactical-objectives"
  | "policies";

function getLayerColors(theme: Theme, slug: string) {
  const key = slug as LayerSlug;
  return theme.colors.layers[key] ?? theme.colors.layers.values;
}

// ── Page layout ──────────────────────────────────────────────────────

export const PageWrapper = styled.div`
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.xl};
`;

// ── Page header ──────────────────────────────────────────────────────

export const PageHeader = styled.div<{ $layerSlug: string }>`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing.md};
  padding: ${({ theme }) => theme.spacing.lg} ${({ theme }) => theme.spacing.xl};
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-left: 4px solid
    ${({ theme, $layerSlug }) => getLayerColors(theme, $layerSlug).primary};
  border-radius: ${({ theme }) => theme.radii.lg};

  @media (max-width: 768px) {
    flex-direction: column;
    align-items: flex-start;
    padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
  }
`;

export const HeaderLeft = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.xs};
  min-width: 0;
`;

export const BackLink = styled.button`
  display: inline-flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.xs};
  background: none;
  border: none;
  cursor: pointer;
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.muted};
  padding: 0;
  transition: color ${({ theme }) => theme.transitions.fast};

  &:hover {
    color: ${({ theme }) => theme.colors.text.primary};
  }
`;

export const LayerTitle = styled.h1<{ $layerSlug: string }>`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xl};
  font-weight: 600;
  color: ${({ theme, $layerSlug }) => getLayerColors(theme, $layerSlug).text};
  margin: 0;
  line-height: 1.3;
`;

// ── Commit timeline ──────────────────────────────────────────────────

export const CommitList = styled.div`
  display: flex;
  flex-direction: column;
`;

export const CommitEntry = styled.div<{ $layerSlug: string }>`
  display: flex;
  gap: ${({ theme }) => theme.spacing.lg};
  padding: ${({ theme }) => theme.spacing.lg} 0;
  position: relative;

  /* Timeline connector line */
  &::before {
    content: "";
    position: absolute;
    left: 7px;
    top: 0;
    bottom: 0;
    width: 2px;
    background: ${({ theme }) => theme.colors.border.default};
  }

  /* Timeline dot */
  &::after {
    content: "";
    position: absolute;
    left: 2px;
    top: ${({ theme }) => theme.spacing.lg};
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: ${({ theme, $layerSlug }) =>
      getLayerColors(theme, $layerSlug).primary};
    border: 2px solid ${({ theme }) => theme.colors.bg.primary};
    z-index: 1;
  }

  &:first-child::before {
    top: ${({ theme }) => theme.spacing.lg};
  }

  &:last-child::before {
    bottom: 50%;
  }

  @media (max-width: 768px) {
    padding: ${({ theme }) => theme.spacing.md} 0;
  }
`;

export const CommitContent = styled.div`
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.xs};
  padding-left: ${({ theme }) => theme.spacing.xl};
`;

export const CommitMessage = styled.p`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.md};
  font-weight: 500;
  color: ${({ theme }) => theme.colors.text.primary};
  line-height: 1.5;
  margin: 0;
`;

export const CommitMeta = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.md};
  flex-wrap: wrap;
`;

export const CommitTimestamp = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.text.muted};
  white-space: nowrap;
`;

export const CommitHash = styled.code`
  font-family: ${({ theme }) => theme.fonts.mono};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.text.muted};
  background: ${({ theme }) => theme.colors.bg.tertiary};
  padding: 1px 6px;
  border-radius: ${({ theme }) => theme.radii.sm};
`;

export const CommitAuthor = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.text.secondary};
`;

// ── Load more ────────────────────────────────────────────────────────

export const LoadMoreWrapper = styled.div`
  display: flex;
  justify-content: center;
  padding: ${({ theme }) => theme.spacing.lg} 0;
`;
