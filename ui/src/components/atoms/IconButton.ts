/**
 * IconButton atom.
 *
 * Square, icon-only button for dismiss buttons, action icons, etc.
 * Variants: ghost (default), outline, danger.
 */
import styled, { css } from "styled-components";

export type IconButtonVariant = "ghost" | "outline" | "danger";
export type IconButtonSize = "sm" | "md" | "lg";

export interface IconButtonProps {
  $variant?: IconButtonVariant;
  $size?: IconButtonSize;
}

const variantStyles = {
  ghost: css`
    background: transparent;
    color: ${({ theme }) => theme.colors.text.secondary};

    &:hover:not(:disabled) {
      background: ${({ theme }) => theme.colors.bg.elevated};
      color: ${({ theme }) => theme.colors.text.primary};
    }
  `,
  outline: css`
    background: transparent;
    color: ${({ theme }) => theme.colors.text.secondary};
    border: 1px solid ${({ theme }) => theme.colors.border.default};

    &:hover:not(:disabled) {
      background: ${({ theme }) => theme.colors.bg.elevated};
      border-color: ${({ theme }) => theme.colors.text.muted};
      color: ${({ theme }) => theme.colors.text.primary};
    }
  `,
  danger: css`
    background: transparent;
    color: ${({ theme }) => theme.colors.text.secondary};

    &:hover:not(:disabled) {
      background: ${({ theme }) => theme.colors.status.error.bg};
      color: ${({ theme }) => theme.colors.accent.red};
    }
  `,
};

const sizeStyles = {
  sm: css`
    width: 28px;
    height: 28px;
    font-size: 14px;
    border-radius: ${({ theme }) => theme.radii.sm};
  `,
  md: css`
    width: 32px;
    height: 32px;
    font-size: 16px;
    border-radius: ${({ theme }) => theme.radii.md};
  `,
  lg: css`
    width: 40px;
    height: 40px;
    font-size: 20px;
    border-radius: ${({ theme }) => theme.radii.lg};
  `,
};

export const IconButton = styled.button<IconButtonProps>`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: none;
  cursor: pointer;
  flex-shrink: 0;
  transition:
    background ${({ theme }) => theme.transitions.fast},
    color ${({ theme }) => theme.transitions.fast},
    border-color ${({ theme }) => theme.transitions.fast};

  /* SVG icons inherit size via 1em */
  svg {
    width: 1em;
    height: 1em;
  }

  ${({ $size = "md" }) => sizeStyles[$size]}
  ${({ $variant = "ghost" }) => variantStyles[$variant]}

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.accent.blue};
    outline-offset: 2px;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    pointer-events: none;
  }
`;
