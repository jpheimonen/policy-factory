/**
 * Input and Textarea atoms.
 *
 * Share base styling via a CSS fragment. Input supports sizes and error state.
 * Textarea is vertically resizable with the same base look.
 */
import styled, { css } from "styled-components";

export type InputSize = "sm" | "md";

export interface InputProps {
  $size?: InputSize;
  $error?: boolean;
}

/**
 * Shared base styles for Input, Textarea, and Select.
 * Exported so other form components can compose with it.
 */
export const baseInputStyles = css`
  width: 100%;
  background: ${({ theme }) => theme.colors.bg.primary};
  color: ${({ theme }) => theme.colors.text.primary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  font-family: ${({ theme }) => theme.fonts.sans};
  transition:
    border-color ${({ theme }) => theme.transitions.fast},
    box-shadow ${({ theme }) => theme.transitions.fast};

  &::placeholder {
    color: ${({ theme }) => theme.colors.text.muted};
  }

  &:focus {
    outline: none;
    border-color: ${({ theme }) => theme.colors.accent.blue};
    box-shadow: 0 0 0 2px ${({ theme }) => theme.colors.status.active.bg};
  }

  &:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
`;

const sizeStyles = {
  sm: css`
    padding: 6px 10px;
    font-size: ${({ theme }) => theme.fontSizes.sm};
    border-radius: ${({ theme }) => theme.radii.sm};
  `,
  md: css`
    padding: 8px 12px;
    font-size: ${({ theme }) => theme.fontSizes.md};
    border-radius: ${({ theme }) => theme.radii.md};
  `,
};

export const Input = styled.input<InputProps>`
  ${baseInputStyles}
  ${({ $size = "md" }) => sizeStyles[$size]}

  ${({ $error, theme }) =>
    $error &&
    css`
      border-color: ${theme.colors.accent.red};

      &:focus {
        border-color: ${theme.colors.accent.red};
        box-shadow: 0 0 0 2px ${theme.colors.status.error.bg};
      }
    `}
`;

export const Textarea = styled.textarea<InputProps>`
  ${baseInputStyles}
  ${({ $size = "md" }) => sizeStyles[$size]}
  resize: vertical;
  min-height: 80px;
  line-height: 1.5;

  ${({ $error, theme }) =>
    $error &&
    css`
      border-color: ${theme.colors.accent.red};

      &:focus {
        border-color: ${theme.colors.accent.red};
        box-shadow: 0 0 0 2px ${theme.colors.status.error.bg};
      }
    `}
`;
