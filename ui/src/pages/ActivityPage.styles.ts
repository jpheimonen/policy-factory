/**
 * Styled components for the Activity Feed page.
 *
 * Layout: page header with filter controls above a scrollable event list.
 * The event list fills available vertical space and scrolls internally.
 */
import styled from "styled-components";

// ── Page layout ──────────────────────────────────────────────────────

export const PageWrapper = styled.div`
  max-width: 800px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.lg};
  height: 100%;
`;

// ── Page header ──────────────────────────────────────────────────────

export const PageHeader = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.md};
`;

export const PageTitle = styled.h1`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xl};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text.primary};
  margin: 0;
`;

// ── Filter controls ──────────────────────────────────────────────────

export const FilterBar = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.md};
  flex-wrap: wrap;

  @media (max-width: 768px) {
    flex-direction: column;
    align-items: stretch;
  }
`;

export const FilterGroup = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
`;

export const FilterLabel = styled.label`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: 500;
  color: ${({ theme }) => theme.colors.text.muted};
  text-transform: uppercase;
  letter-spacing: 0.04em;
  white-space: nowrap;
`;

// ── Category button group ────────────────────────────────────────────

export const CategoryButtons = styled.div`
  display: flex;
  gap: 1px;
  background: ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.md};
  overflow: hidden;
`;

export const CategoryButton = styled.button<{ $active: boolean }>`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: 500;
  padding: 6px 12px;
  border: none;
  cursor: pointer;
  white-space: nowrap;
  transition: background ${({ theme }) => theme.transitions.fast},
    color ${({ theme }) => theme.transitions.fast};

  background: ${({ theme, $active }) =>
    $active ? theme.colors.accent.blue : theme.colors.bg.secondary};
  color: ${({ theme, $active }) =>
    $active ? "#fff" : theme.colors.text.secondary};

  &:hover {
    background: ${({ theme, $active }) =>
      $active ? theme.colors.accent.blue : theme.colors.bg.tertiary};
  }
`;

// ── Event list ───────────────────────────────────────────────────────

export const EventList = styled.div`
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.lg};
  overflow: hidden;
  flex: 1;
  min-height: 0;
  overflow-y: auto;
`;

// ── Load more ────────────────────────────────────────────────────────

export const LoadMoreWrapper = styled.div`
  display: flex;
  justify-content: center;
  padding: ${({ theme }) => theme.spacing.lg};
  border-top: 1px solid ${({ theme }) => theme.colors.border.subtle};
`;
