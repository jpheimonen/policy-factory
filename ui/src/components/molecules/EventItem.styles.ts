/**
 * Styled components for the EventItem molecule.
 *
 * Compact event rows with category-specific left-border accents.
 * New events arriving in real-time get a subtle fade-in animation.
 */
import styled, { keyframes, css } from "styled-components";
import type { EventCategory } from "@/types/events.ts";

// ── Fade-in animation ────────────────────────────────────────────────

const fadeIn = keyframes`
  from {
    opacity: 0;
    transform: translateY(-4px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
`;

// ── Category accent colors ───────────────────────────────────────────

function getCategoryColor(
  theme: { colors: { accent: { blue: string; red: string; purple: string; cyan: string; green: string; yellow: string }; status: { pending: { text: string } } } },
  category: EventCategory | null,
): string {
  switch (category) {
    case "cascade":
      return theme.colors.accent.blue;
    case "heartbeat":
      return theme.colors.accent.purple;
    case "idea":
      return theme.colors.accent.green;
    case "system":
      return theme.colors.accent.yellow;
    default:
      return theme.colors.status.pending.text;
  }
}

// ── Event item container ─────────────────────────────────────────────

export const EventItemWrapper = styled.div<{
  $category: EventCategory | null;
  $isNew?: boolean;
}>`
  display: flex;
  align-items: flex-start;
  gap: ${({ theme }) => theme.spacing.md};
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
  border-left: 3px solid
    ${({ theme, $category }) => getCategoryColor(theme, $category)};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border.subtle};
  transition: background ${({ theme }) => theme.transitions.fast};

  ${({ $isNew }) =>
    $isNew &&
    css`
      animation: ${fadeIn} 0.3s ease-out;
    `}

  &:hover {
    background: ${({ theme }) => theme.colors.bg.tertiary};
  }

  &:last-child {
    border-bottom: none;
  }

  @media (max-width: 768px) {
    padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
    gap: ${({ theme }) => theme.spacing.sm};
  }
`;

// ── Icon ──────────────────────────────────────────────────────────────

export const EventIcon = styled.div<{ $category: EventCategory | null }>`
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  color: ${({ theme, $category }) => getCategoryColor(theme, $category)};
  opacity: 0.8;
`;

// ── Content area ─────────────────────────────────────────────────────

export const EventContent = styled.div`
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
`;

export const EventTopRow = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
  flex-wrap: wrap;
`;

export const EventDescription = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.primary};
  line-height: 1.4;
`;

export const EventTimestamp = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.text.muted};
  white-space: nowrap;
  flex-shrink: 0;
  margin-left: auto;
`;

export const EventMeta = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
  flex-wrap: wrap;
`;

export const EventErrorText = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.status.error.text};
  line-height: 1.4;
`;

// ── Layer badge ──────────────────────────────────────────────────────

export const LayerBadge = styled.span<{ $layerSlug: string }>`
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: 500;
  border-radius: ${({ theme }) => theme.radii.sm};
  white-space: nowrap;
  background: ${({ theme, $layerSlug }) => {
    const key = $layerSlug as keyof typeof theme.colors.layers;
    const layer = theme.colors.layers[key];
    return layer ? layer.bg : theme.colors.status.pending.bg;
  }};
  color: ${({ theme, $layerSlug }) => {
    const key = $layerSlug as keyof typeof theme.colors.layers;
    const layer = theme.colors.layers[key];
    return layer ? layer.text : theme.colors.status.pending.text;
  }};
`;
