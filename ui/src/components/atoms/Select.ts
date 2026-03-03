/**
 * Select atom.
 *
 * Styled consistently with Input, with a custom dropdown arrow.
 * Supports sizes and error state.
 */
import styled, { css } from "styled-components";
import { baseInputStyles } from "./Input.ts";
import type { InputProps } from "./Input.ts";

const sizeStyles = {
  sm: css`
    padding: 6px 28px 6px 10px;
    font-size: ${({ theme }) => theme.fontSizes.sm};
    border-radius: ${({ theme }) => theme.radii.sm};
  `,
  md: css`
    padding: 8px 32px 8px 12px;
    font-size: ${({ theme }) => theme.fontSizes.md};
    border-radius: ${({ theme }) => theme.radii.md};
  `,
};

export const Select = styled.select<InputProps>`
  ${baseInputStyles}
  ${({ $size = "md" }) => sizeStyles[$size]}
  appearance: none;
  cursor: pointer;

  /* Custom dropdown arrow via SVG data URL */
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%239090a8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 10px center;

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
