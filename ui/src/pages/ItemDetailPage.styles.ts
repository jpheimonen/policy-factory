/**
 * Styled components for the Item Detail page.
 *
 * Provides layout and styling for both view mode and edit mode.
 * Uses theme tokens for all colours, spacing, fonts, and borders.
 * Follows the co-located styles pattern consistent with LayerDetailPage.styles.ts.
 */
import styled, { css } from "styled-components";
import type { Theme } from "@/styles/theme.ts";

// ── Layer color helper ───────────────────────────────────────────────

type LayerSlug =
  | "values"
  | "situational-awareness"
  | "strategic-objectives"
  | "tactical-objectives"
  | "policies";

function getLayerColors(theme: Theme, slug: string) {
  const key = slug as LayerSlug;
  return theme.colors.layers[key] ?? theme.colors.layers.values;
}

// ── Page layout ──────────────────────────────────────────────────────

/** Outer container that handles the sidebar layout shift */
export const PageContainer = styled.div<{ $sidebarOpen: boolean }>`
  display: flex;
  justify-content: center;
  transition: padding-right ${({ theme }) => theme.transitions.normal};

  /* When sidebar is open, add padding to shift content left */
  ${({ $sidebarOpen }) =>
    $sidebarOpen &&
    css`
      padding-right: 420px;

      @media (max-width: 1200px) {
        padding-right: 360px;
      }

      @media (max-width: 900px) {
        /* On smaller screens, sidebar overlays instead of pushing */
        padding-right: 0;
      }
    `}
`;

export const PageWrapper = styled.div<{ $sidebarOpen?: boolean }>`
  max-width: 800px;
  width: 100%;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.xl};
  transition: max-width ${({ theme }) => theme.transitions.normal};

  /* When sidebar is open, allow content to be slightly narrower if needed */
  ${({ $sidebarOpen }) =>
    $sidebarOpen &&
    css`
      @media (max-width: 1400px) {
        max-width: 700px;
      }

      @media (max-width: 1200px) {
        max-width: 600px;
      }
    `}
`;

// ── Page header ──────────────────────────────────────────────────────

export const PageHeader = styled.div<{ $layerSlug: string }>`
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: ${({ theme }) => theme.spacing.md};
  padding: ${({ theme }) => theme.spacing.lg} ${({ theme }) => theme.spacing.xl};
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-left: 4px solid
    ${({ theme, $layerSlug }) => getLayerColors(theme, $layerSlug).primary};
  border-radius: ${({ theme }) => theme.radii.lg};

  @media (max-width: 768px) {
    flex-direction: column;
    align-items: flex-start;
    padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
  }
`;

export const HeaderLeft = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.xs};
  min-width: 0;
  flex: 1;
`;

export const BackLink = styled.button`
  display: inline-flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.xs};
  background: none;
  border: none;
  cursor: pointer;
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.muted};
  padding: 0;
  transition: color ${({ theme }) => theme.transitions.fast};

  &:hover {
    color: ${({ theme }) => theme.colors.text.primary};
  }
`;

export const LayerSubtitle = styled.span<{ $layerSlug: string }>`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: 500;
  color: ${({ theme, $layerSlug }) => getLayerColors(theme, $layerSlug).text};
  text-transform: uppercase;
  letter-spacing: 0.04em;
`;

export const ItemTitleHeading = styled.h1`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xl};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text.primary};
  margin: 0;
  line-height: 1.3;
`;

export const HeaderRight = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
  flex-shrink: 0;

  @media (max-width: 768px) {
    width: 100%;
    justify-content: flex-end;
  }
`;

export const SaveIndicator = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.status.success.text};
  font-weight: 500;
`;

// ── Section containers ───────────────────────────────────────────────

export const Section = styled.section`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.md};
`;

export const SectionTitle = styled.h2`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.base};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text.primary};
  margin: 0;
`;

// ── Frontmatter fields ───────────────────────────────────────────────

export const FieldGrid = styled.div`
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: ${({ theme }) => theme.spacing.lg};

  @media (max-width: 768px) {
    grid-template-columns: 1fr;
    gap: ${({ theme }) => theme.spacing.md};
  }
`;

export const FieldItem = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.xs};
`;

export const FieldLabel = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: 500;
  color: ${({ theme }) => theme.colors.text.muted};
  text-transform: uppercase;
  letter-spacing: 0.04em;
`;

export const FieldValue = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.md};
  color: ${({ theme }) => theme.colors.text.primary};
  line-height: 1.5;
  word-break: break-word;
`;

// ── Body section ─────────────────────────────────────────────────────

export const BodyWrapper = styled.div`
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.lg};
  padding: ${({ theme }) => theme.spacing.xl};

  @media (max-width: 768px) {
    padding: ${({ theme }) => theme.spacing.lg};
  }
`;

export const EmptyBody = styled.p`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.md};
  color: ${({ theme }) => theme.colors.text.muted};
  font-style: italic;
  margin: 0;
`;

// ── Cross-layer references ───────────────────────────────────────────

export const ReferenceGroup = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.sm};
`;

export const ReferenceGroupTitle = styled.h3`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text.secondary};
  margin: 0;
`;

export const ReferenceLink = styled.button<{ $layerSlug: string }>`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-left: 3px solid
    ${({ theme, $layerSlug }) => getLayerColors(theme, $layerSlug).primary};
  border-radius: ${({ theme }) => theme.radii.md};
  padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
  cursor: pointer;
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.primary};
  text-align: left;
  width: 100%;
  transition:
    background ${({ theme }) => theme.transitions.fast},
    border-color ${({ theme }) => theme.transitions.fast};

  &:hover {
    background: ${({ theme }) => theme.colors.bg.tertiary};
    border-color: ${({ theme, $layerSlug }) =>
      getLayerColors(theme, $layerSlug).primary};
  }
`;

export const ReferenceLayerTag = styled.span<{ $layerSlug: string }>`
  font-size: ${({ theme }) => theme.fontSizes.xs};
  font-weight: 500;
  color: ${({ theme, $layerSlug }) => getLayerColors(theme, $layerSlug).text};
  flex-shrink: 0;
`;

// ── Attribution ──────────────────────────────────────────────────────

export const AttributionBar = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.md};
  flex-wrap: wrap;
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
  background: ${({ theme }) => theme.colors.bg.secondary};
  border: 1px solid ${({ theme }) => theme.colors.border.subtle};
  border-radius: ${({ theme }) => theme.radii.md};
`;

export const AttributionItem = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.text.muted};
`;

// ── Edit mode ────────────────────────────────────────────────────────

export const EditBody = styled.textarea`
  width: 100%;
  min-height: 300px;
  resize: vertical;
  background: ${({ theme }) => theme.colors.bg.primary};
  color: ${({ theme }) => theme.colors.text.primary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.md};
  font-family: ${({ theme }) => theme.fonts.mono};
  font-size: ${({ theme }) => theme.fontSizes.md};
  line-height: 1.6;
  padding: ${({ theme }) => theme.spacing.lg};
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
`;

export const ErrorBanner = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
  background: ${({ theme }) => theme.colors.status.error.bg};
  border: 1px solid ${({ theme }) => theme.colors.status.error.border};
  border-radius: ${({ theme }) => theme.radii.md};
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.status.error.text};
`;

// ── Read-only field indicator ────────────────────────────────────────

export const ReadOnlyValue = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.md};
  color: ${({ theme }) => theme.colors.text.muted};
  padding: 8px 12px;
  background: ${({ theme }) => theme.colors.bg.tertiary};
  border: 1px solid ${({ theme }) => theme.colors.border.subtle};
  border-radius: ${({ theme }) => theme.radii.md};
`;

// ── Conversation toggle button ────────────────────────────────────────

export const ConversationToggle = styled.button<{ $active: boolean }>`
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: ${({ theme }) => theme.spacing.xs};
  padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
  background: ${({ theme, $active }) =>
    $active ? theme.colors.accent.blue : "transparent"};
  color: ${({ theme, $active }) =>
    $active ? "#fff" : theme.colors.text.secondary};
  border: 1px solid
    ${({ theme, $active }) =>
      $active ? theme.colors.accent.blue : theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.md};
  cursor: pointer;
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  font-weight: 500;
  transition:
    background ${({ theme }) => theme.transitions.fast},
    color ${({ theme }) => theme.transitions.fast},
    border-color ${({ theme }) => theme.transitions.fast};

  &:hover {
    background: ${({ theme, $active }) =>
      $active ? theme.colors.accent.blue : theme.colors.bg.elevated};
    color: ${({ theme, $active }) =>
      $active ? "#fff" : theme.colors.text.primary};
    border-color: ${({ theme, $active }) =>
      $active ? theme.colors.accent.blue : theme.colors.text.muted};
  }

  &:focus-visible {
    outline: 2px solid ${({ theme }) => theme.colors.accent.blue};
    outline-offset: 2px;
  }

  svg {
    width: 16px;
    height: 16px;
  }
`;

// ── AI edit conflict banner ─────────────────────────────────────────────

export const ConflictBanner = styled.div`
  display: flex;
  align-items: flex-start;
  gap: ${({ theme }) => theme.spacing.md};
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
  background: ${({ theme }) => theme.colors.status.warning.bg};
  border: 1px solid ${({ theme }) => theme.colors.status.warning.border};
  border-radius: ${({ theme }) => theme.radii.md};
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.status.warning.text};

  @media (max-width: 768px) {
    flex-direction: column;
    gap: ${({ theme }) => theme.spacing.sm};
  }
`;

export const ConflictBannerIcon = styled.span`
  display: flex;
  align-items: center;
  flex-shrink: 0;
  color: ${({ theme }) => theme.colors.accent.yellow};

  svg {
    width: 18px;
    height: 18px;
  }
`;

export const ConflictBannerContent = styled.div`
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.xs};
`;

export const ConflictBannerTitle = styled.strong`
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text.primary};
`;

export const ConflictBannerText = styled.p`
  margin: 0;
  line-height: 1.5;
`;

export const ConflictBannerActions = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
  flex-shrink: 0;

  @media (max-width: 768px) {
    width: 100%;
    justify-content: flex-end;
  }
`;
