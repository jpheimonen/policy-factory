/**
 * Text atom.
 *
 * Styled text component with variant and size props for consistent typography.
 * Variants: heading, body, label, caption, muted.
 * Renders as a <span> by default; use `as="p"`, `as="h2"`, etc. for semantic HTML.
 */
import styled, { css } from "styled-components";

export type TextVariant = "heading" | "body" | "label" | "caption" | "muted";
export type TextSize = "xs" | "sm" | "md" | "base" | "lg" | "xl";

export interface TextProps {
  $variant?: TextVariant;
  $size?: TextSize;
  $weight?: 400 | 500 | 600;
}

const variantStyles = {
  heading: css`
    color: ${({ theme }) => theme.colors.text.primary};
    font-weight: 600;
    line-height: 1.3;
  `,
  body: css`
    color: ${({ theme }) => theme.colors.text.primary};
    font-weight: 400;
    line-height: 1.6;
  `,
  label: css`
    color: ${({ theme }) => theme.colors.text.secondary};
    font-weight: 500;
    line-height: 1.4;
    letter-spacing: 0.01em;
  `,
  caption: css`
    color: ${({ theme }) => theme.colors.text.muted};
    font-weight: 400;
    line-height: 1.4;
  `,
  muted: css`
    color: ${({ theme }) => theme.colors.text.muted};
    font-weight: 400;
    line-height: 1.6;
  `,
};

export const Text = styled.span<TextProps>`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ $size, theme }) => ($size ? theme.fontSizes[$size] : "inherit")};

  ${({ $variant = "body" }) => variantStyles[$variant]}

  ${({ $weight }) =>
    $weight !== undefined &&
    css`
      font-weight: ${$weight};
    `}
`;
