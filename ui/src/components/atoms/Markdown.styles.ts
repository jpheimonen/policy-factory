/**
 * Styles for the Markdown rendering component.
 *
 * Provides theme-aware typography for rendered markdown content.
 * Covers headings, paragraphs, lists, blockquotes, code blocks,
 * tables, links, images, and GFM extensions (task lists, strikethrough).
 *
 * Follows the cc-runner Markdown.styles.ts pattern, adapted for
 * Policy Factory's dual-theme design system.
 */
import styled from "styled-components";

export const Container = styled.div`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.md};
  line-height: 1.7;
  color: ${({ theme }) => theme.colors.text.primary};
  word-wrap: break-word;

  /* ── Headings ────────────────────────────────────────────────────── */

  h1 {
    font-size: 1.75em;
    font-weight: 600;
    margin: 0 0 ${({ theme }) => theme.spacing.lg};
    padding-bottom: ${({ theme }) => theme.spacing.sm};
    border-bottom: 1px solid ${({ theme }) => theme.colors.border.default};
    line-height: 1.3;
  }

  h2 {
    font-size: 1.4em;
    font-weight: 600;
    margin: ${({ theme }) => theme.spacing.xl} 0
      ${({ theme }) => theme.spacing.md};
    padding-bottom: 6px;
    border-bottom: 1px solid ${({ theme }) => theme.colors.border.default};
    line-height: 1.3;
  }

  h3 {
    font-size: 1.2em;
    font-weight: 600;
    margin: ${({ theme }) => theme.spacing.lg} 0
      ${({ theme }) => theme.spacing.sm};
    line-height: 1.4;
  }

  h4,
  h5,
  h6 {
    font-size: 1em;
    font-weight: 600;
    margin: ${({ theme }) => theme.spacing.lg} 0
      ${({ theme }) => theme.spacing.sm};
    line-height: 1.4;
  }

  /* ── Paragraphs ──────────────────────────────────────────────────── */

  p {
    margin: 0 0 ${({ theme }) => theme.spacing.md};
  }

  /* ── Lists ───────────────────────────────────────────────────────── */

  ul,
  ol {
    margin: 0 0 ${({ theme }) => theme.spacing.md};
    padding-left: 24px;
  }

  li {
    margin: ${({ theme }) => theme.spacing.xs} 0;
  }

  li > ul,
  li > ol {
    margin: ${({ theme }) => theme.spacing.xs} 0;
  }

  /* Task list checkboxes (GFM) */
  li input[type="checkbox"] {
    margin-right: ${({ theme }) => theme.spacing.sm};
  }

  li.task-list-item {
    list-style: none;
    margin-left: -24px;
    padding-left: 24px;
  }

  /* ── Blockquotes ─────────────────────────────────────────────────── */

  blockquote {
    margin: 0 0 ${({ theme }) => theme.spacing.md};
    padding: ${({ theme }) => `${theme.spacing.sm} ${theme.spacing.lg}`};
    border-left: 4px solid ${({ theme }) => theme.colors.accent.blue};
    background: ${({ theme }) => theme.colors.bg.tertiary};
    color: ${({ theme }) => theme.colors.text.secondary};

    p:last-child {
      margin-bottom: 0;
    }
  }

  /* ── Horizontal rules ────────────────────────────────────────────── */

  hr {
    border: none;
    border-top: 1px solid ${({ theme }) => theme.colors.border.default};
    margin: ${({ theme }) => theme.spacing.xl} 0;
  }

  /* ── Links ───────────────────────────────────────────────────────── */

  a {
    color: ${({ theme }) => theme.colors.accent.blue};
    text-decoration: none;

    &:hover {
      text-decoration: underline;
    }
  }

  /* ── Tables (GFM) ───────────────────────────────────────────────── */

  table {
    width: 100%;
    border-collapse: collapse;
    margin: 0 0 ${({ theme }) => theme.spacing.lg};
    font-size: ${({ theme }) => theme.fontSizes.sm};
  }

  th,
  td {
    padding: ${({ theme }) => `${theme.spacing.sm} ${theme.spacing.md}`};
    border: 1px solid ${({ theme }) => theme.colors.border.default};
    text-align: left;
  }

  th {
    background: ${({ theme }) => theme.colors.bg.tertiary};
    font-weight: 600;
  }

  tr:nth-child(even) {
    background: ${({ theme }) => theme.colors.bg.secondary};
  }

  /* ── Code blocks ─────────────────────────────────────────────────── */

  pre {
    margin: 0 0 ${({ theme }) => theme.spacing.lg};
    padding: ${({ theme }) => theme.spacing.md};
    background: ${({ theme }) => theme.colors.bg.primary};
    border: 1px solid ${({ theme }) => theme.colors.border.default};
    border-radius: ${({ theme }) => theme.radii.md};
    overflow-x: auto;

    code {
      font-family: ${({ theme }) => theme.fonts.mono};
      font-size: ${({ theme }) => theme.fontSizes.xs};
      line-height: 1.5;
      background: transparent;
      padding: 0;
      color: inherit;
    }
  }

  /* ── Strikethrough (GFM) ─────────────────────────────────────────── */

  del {
    color: ${({ theme }) => theme.colors.text.muted};
  }

  /* ── Images ──────────────────────────────────────────────────────── */

  img {
    max-width: 100%;
    border-radius: ${({ theme }) => theme.radii.sm};
  }

  /* ── Strong and emphasis ─────────────────────────────────────────── */

  strong {
    font-weight: 600;
  }
`;

export const InlineCode = styled.code`
  background: ${({ theme }) => theme.colors.bg.tertiary};
  padding: 2px 6px;
  border-radius: 3px;
  font-family: ${({ theme }) => theme.fonts.mono};
  font-size: 0.9em;
  color: ${({ theme }) => theme.colors.accent.purple};
`;
