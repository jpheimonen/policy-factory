/**
 * Card atom.
 *
 * Default: subtle border, themed background.
 * Elevated: slight shadow, elevated background.
 * Interactive: hover effect for clickable cards (e.g., layer cards on stack overview).
 */
import styled, { css } from "styled-components";

export type CardPadding = "none" | "sm" | "md" | "lg";

export interface CardProps {
  $elevated?: boolean;
  $interactive?: boolean;
  $padding?: CardPadding;
}

const paddingMap = {
  none: "0",
  sm: "12px",
  md: "16px",
  lg: "24px",
};

export const Card = styled.div<CardProps>`
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.lg};
  padding: ${({ $padding = "md" }) => paddingMap[$padding]};
  transition:
    background ${({ theme }) => theme.transitions.normal},
    border-color ${({ theme }) => theme.transitions.normal},
    box-shadow ${({ theme }) => theme.transitions.normal},
    transform ${({ theme }) => theme.transitions.normal};

  ${({ $elevated, theme }) =>
    $elevated &&
    css`
      background: ${theme.colors.bg.elevated};
      box-shadow: ${theme.shadows.md};
      border-color: ${theme.colors.border.subtle};
    `}

  ${({ $interactive, theme }) =>
    $interactive &&
    css`
      cursor: pointer;

      &:hover {
        border-color: ${theme.colors.text.muted};
        box-shadow: ${theme.shadows.sm};
        transform: translateY(-1px);
      }

      &:active {
        transform: translateY(0);
      }
    `}
`;
