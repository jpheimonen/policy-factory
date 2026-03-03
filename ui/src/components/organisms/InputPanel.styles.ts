/**
 * Styled components for the InputPanel floating element.
 *
 * A floating action button (FAB) in the bottom-right corner that expands
 * to reveal a text input panel for submitting free-text input.
 */
import styled, { css, keyframes } from "styled-components";

// ── Animations ─────────────────────────────────────────────────────────

const fadeIn = keyframes`
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
`;

const fadeOut = keyframes`
  from { opacity: 1; transform: translateY(0); }
  to   { opacity: 0; transform: translateY(8px); }
`;

// ── FAB trigger button ─────────────────────────────────────────────────

export const FabButton = styled.button`
  position: fixed;
  bottom: ${({ theme }) => theme.spacing.xl};
  right: ${({ theme }) => theme.spacing.xl};
  width: 52px;
  height: 52px;
  border-radius: 50%;
  border: none;
  background: ${({ theme }) => theme.colors.accent.blue};
  color: #ffffff;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: ${({ theme }) => theme.zIndices.sticky};
  box-shadow: ${({ theme }) => theme.shadows.lg};
  transition: transform ${({ theme }) => theme.transitions.fast},
    box-shadow ${({ theme }) => theme.transitions.fast};

  &:hover {
    transform: scale(1.05);
    box-shadow: ${({ theme }) => theme.shadows.lg}, 0 0 0 3px ${({ theme }) => theme.colors.accent.blue}33;
  }

  &:active {
    transform: scale(0.97);
  }

  svg {
    width: 22px;
    height: 22px;
  }
`;

// ── Expanded panel ─────────────────────────────────────────────────────

export const PanelOverlay = styled.div`
  position: fixed;
  inset: 0;
  z-index: ${({ theme }) => theme.zIndices.sticky + 1};
  /* No background — panel floats freely */
`;

export const PanelContainer = styled.div<{ $closing?: boolean }>`
  position: fixed;
  bottom: ${({ theme }) => theme.spacing.xl};
  right: ${({ theme }) => theme.spacing.xl};
  width: 400px;
  max-width: calc(100vw - 2 * ${({ theme }) => theme.spacing.xl});
  z-index: ${({ theme }) => theme.zIndices.sticky + 2};
  background: ${({ theme }) => theme.colors.bg.elevated};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.lg};
  box-shadow: ${({ theme }) => theme.shadows.lg};
  display: flex;
  flex-direction: column;
  overflow: hidden;

  ${({ $closing }) =>
    $closing
      ? css`
          animation: ${fadeOut} 0.15s ease-out forwards;
        `
      : css`
          animation: ${fadeIn} 0.2s ease-out;
        `}
`;

export const PanelHeader = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border.subtle};
`;

export const PanelTitle = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.md};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text.primary};
`;

export const PanelBody = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.sm};
  padding: ${({ theme }) => theme.spacing.md};
`;

export const PanelTextarea = styled.textarea`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.md};
  color: ${({ theme }) => theme.colors.text.primary};
  background: ${({ theme }) => theme.colors.bg.primary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.md};
  padding: ${({ theme }) => theme.spacing.sm};
  min-height: 80px;
  max-height: 200px;
  resize: vertical;
  outline: none;
  line-height: 1.5;

  &::placeholder {
    color: ${({ theme }) => theme.colors.text.muted};
  }

  &:focus {
    border-color: ${({ theme }) => theme.colors.accent.blue};
    box-shadow: 0 0 0 2px ${({ theme }) => theme.colors.accent.blue}33;
  }
`;

export const PanelActions = styled.div`
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: ${({ theme }) => theme.spacing.sm};
`;

// ── Result display ─────────────────────────────────────────────────────

export const ResultDisplay = styled.div<{
  $variant: "success" | "error";
}>`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
  border-radius: ${({ theme }) => theme.radii.md};
  background: ${({ theme, $variant }) =>
    $variant === "success"
      ? theme.colors.status.success.bg
      : theme.colors.status.error.bg};
  color: ${({ theme, $variant }) =>
    $variant === "success"
      ? theme.colors.status.success.text
      : theme.colors.status.error.text};
  border: 1px solid
    ${({ theme, $variant }) =>
      $variant === "success"
        ? theme.colors.status.success.border
        : theme.colors.status.error.border};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.xs};
`;

export const ResultLink = styled.a`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.accent.blue};
  text-decoration: none;
  cursor: pointer;

  &:hover {
    text-decoration: underline;
  }
`;
