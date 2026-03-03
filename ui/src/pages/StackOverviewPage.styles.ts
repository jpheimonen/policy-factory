/**
 * Styled components for the Stack Overview page.
 *
 * Layer cards are displayed as a vertical stack ordered bottom (Values) to top (Policies).
 * Each card has an identity colour accent via a left border, derived from the layer slug.
 */
import styled, { css, keyframes } from "styled-components";
import type { Theme } from "@/styles/theme.ts";

// ── Page layout ──────────────────────────────────────────────────────

export const PageWrapper = styled.div`
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.lg};
`;

export const PageTitle = styled.h1`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xl};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text.primary};
  margin: 0 0 ${({ theme }) => theme.spacing.sm} 0;
`;

// ── Layer card stack ─────────────────────────────────────────────────

export const LayerStack = styled.div`
  display: flex;
  flex-direction: column-reverse;
  gap: ${({ theme }) => theme.spacing.md};
`;

// ── Helpers for layer identity colour ────────────────────────────────

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

// ── Layer card ───────────────────────────────────────────────────────

export const LayerCard = styled.div<{ $layerSlug: string }>`
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-left: 3px solid
    ${({ theme, $layerSlug }) => getLayerColors(theme, $layerSlug).primary};
  border-radius: ${({ theme }) => theme.radii.lg};
  padding: ${({ theme }) => theme.spacing.lg} ${({ theme }) => theme.spacing.xl};
  cursor: pointer;
  transition: background ${({ theme }) => theme.transitions.normal},
    border-color ${({ theme }) => theme.transitions.normal},
    box-shadow ${({ theme }) => theme.transitions.normal},
    transform ${({ theme }) => theme.transitions.normal};

  &:hover {
    background: ${({ theme }) => theme.colors.bg.tertiary};
    border-color: ${({ theme, $layerSlug }) =>
      getLayerColors(theme, $layerSlug).primary};
    box-shadow: ${({ theme }) => theme.shadows.sm};
    transform: translateY(-1px);
  }

  &:active {
    transform: translateY(0);
  }

  @media (max-width: 768px) {
    padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
  }
`;

export const LayerCardHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing.md};
  margin-bottom: ${({ theme }) => theme.spacing.sm};
`;

export const LayerName = styled.span<{ $layerSlug: string }>`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.lg};
  font-weight: 600;
  color: ${({ theme, $layerSlug }) =>
    getLayerColors(theme, $layerSlug).text};
`;

export const LayerMeta = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.md};
  flex-shrink: 0;
`;

export const MetaItem = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.text.muted};
  white-space: nowrap;
`;

export const NarrativePreview = styled.p`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.secondary};
  line-height: 1.5;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
`;

// ── Skeleton loading placeholders ────────────────────────────────────

const shimmer = keyframes`
  0% { background-position: -200px 0; }
  100% { background-position: calc(200px + 100%) 0; }
`;

const skeletonBase = css`
  background: ${({ theme }) => theme.colors.bg.tertiary};
  background-image: linear-gradient(
    90deg,
    ${({ theme }) => theme.colors.bg.tertiary} 0%,
    ${({ theme }) => theme.colors.bg.elevated} 40%,
    ${({ theme }) => theme.colors.bg.tertiary} 80%
  );
  background-size: 200px 100%;
  background-repeat: no-repeat;
  animation: ${shimmer} 1.5s ease-in-out infinite;
  border-radius: ${({ theme }) => theme.radii.sm};
`;

export const SkeletonCard = styled.div`
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-left: 3px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.lg};
  padding: ${({ theme }) => theme.spacing.lg} ${({ theme }) => theme.spacing.xl};
`;

export const SkeletonLine = styled.div<{ $width?: string; $height?: string }>`
  ${skeletonBase}
  width: ${({ $width }) => $width ?? "100%"};
  height: ${({ $height }) => $height ?? "14px"};
  margin-bottom: ${({ theme }) => theme.spacing.sm};
`;

// ── Error state ──────────────────────────────────────────────────────

export const ErrorWrapper = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: ${({ theme }) => theme.spacing.md};
  padding: ${({ theme }) => theme.spacing.xxl};
  text-align: center;
`;
