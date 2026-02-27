/**
 * Badge atom.
 *
 * Small, rounded, inline display for status indicators, labels, counts.
 * Variants: info (blue), success (green), warning (yellow), error (red), neutral (muted).
 */
import styled, { css } from "styled-components";

export type BadgeVariant = "info" | "success" | "warning" | "error" | "neutral";

export interface BadgeProps {
  $variant?: BadgeVariant;
}

const variantStyles = {
  info: css`
    background: ${({ theme }) => theme.colors.status.active.bg};
    color: ${({ theme }) => theme.colors.status.active.text};
    border-color: ${({ theme }) => theme.colors.status.active.border};
  `,
  success: css`
    background: ${({ theme }) => theme.colors.status.success.bg};
    color: ${({ theme }) => theme.colors.status.success.text};
    border-color: ${({ theme }) => theme.colors.status.success.border};
  `,
  warning: css`
    background: ${({ theme }) => theme.colors.status.warning.bg};
    color: ${({ theme }) => theme.colors.status.warning.text};
    border-color: ${({ theme }) => theme.colors.status.warning.border};
  `,
  error: css`
    background: ${({ theme }) => theme.colors.status.error.bg};
    color: ${({ theme }) => theme.colors.status.error.text};
    border-color: ${({ theme }) => theme.colors.status.error.border};
  `,
  neutral: css`
    background: ${({ theme }) => theme.colors.status.pending.bg};
    color: ${({ theme }) => theme.colors.status.pending.text};
    border-color: ${({ theme }) => theme.colors.status.pending.border};
  `,
};

export const Badge = styled.span<BadgeProps>`
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: 500;
  line-height: 1.4;
  border-radius: ${({ theme }) => theme.radii.xl};
  border: 1px solid transparent;
  white-space: nowrap;

  ${({ $variant = "neutral" }) => variantStyles[$variant]}
`;
