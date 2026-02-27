/**
 * Button atom.
 *
 * Variants: primary, secondary, danger, ghost, outline
 * Sizes: sm, md, lg
 * States: hover, focus, disabled, loading
 * Supports $fullWidth for block-level layout.
 */
import styled, { css, keyframes } from "styled-components";

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost" | "outline";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps {
  $variant?: ButtonVariant;
  $size?: ButtonSize;
  $loading?: boolean;
  $fullWidth?: boolean;
}

const spin = keyframes`
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
`;

const variantStyles = {
  primary: css`
    background: ${({ theme }) => theme.colors.accent.blue};
    color: #ffffff;

    &:hover:not(:disabled) {
      filter: brightness(1.15);
    }
  `,
  secondary: css`
    background: ${({ theme }) => theme.colors.bg.elevated};
    color: ${({ theme }) => theme.colors.text.primary};
    border: 1px solid ${({ theme }) => theme.colors.border.default};

    &:hover:not(:disabled) {
      background: ${({ theme }) => theme.colors.bg.tertiary};
      border-color: ${({ theme }) => theme.colors.text.muted};
    }
  `,
  danger: css`
    background: ${({ theme }) => theme.colors.accent.red};
    color: #ffffff;

    &:hover:not(:disabled) {
      opacity: 0.9;
    }
  `,
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
    color: ${({ theme }) => theme.colors.text.primary};
    border: 1px solid ${({ theme }) => theme.colors.border.default};

    &:hover:not(:disabled) {
      background: ${({ theme }) => theme.colors.bg.elevated};
      border-color: ${({ theme }) => theme.colors.text.muted};
    }
  `,
};

const sizeStyles = {
  sm: css`
    padding: 4px 10px;
    font-size: ${({ theme }) => theme.fontSizes.sm};
    border-radius: ${({ theme }) => theme.radii.sm};
    gap: 4px;
  `,
  md: css`
    padding: 8px 16px;
    font-size: ${({ theme }) => theme.fontSizes.md};
    border-radius: ${({ theme }) => theme.radii.md};
    gap: 6px;
  `,
  lg: css`
    padding: 12px 24px;
    font-size: ${({ theme }) => theme.fontSizes.base};
    border-radius: ${({ theme }) => theme.radii.lg};
    gap: 8px;
  `,
};

export const Button = styled.button<ButtonProps>`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: ${({ theme }) => theme.fonts.sans};
  font-weight: 500;
  border: none;
  cursor: pointer;
  white-space: nowrap;
  transition:
    background ${({ theme }) => theme.transitions.fast},
    color ${({ theme }) => theme.transitions.fast},
    border-color ${({ theme }) => theme.transitions.fast},
    opacity ${({ theme }) => theme.transitions.fast};

  ${({ $size = "md" }) => sizeStyles[$size]}
  ${({ $variant = "primary" }) => variantStyles[$variant]}

  ${({ $fullWidth }) =>
    $fullWidth &&
    css`
      width: 100%;
    `}

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.accent.blue};
    outline-offset: 2px;
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    pointer-events: none;
  }

  ${({ $loading, theme }) =>
    $loading &&
    css`
      pointer-events: none;
      position: relative;
      color: transparent !important;

      &::after {
        content: "";
        position: absolute;
        width: 14px;
        height: 14px;
        border: 2px solid ${theme.colors.text.primary};
        border-right-color: transparent;
        border-radius: 50%;
        animation: ${spin} 0.6s linear infinite;
      }
    `}
`;
