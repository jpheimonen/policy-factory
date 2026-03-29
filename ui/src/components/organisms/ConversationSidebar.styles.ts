/**
 * Styled components for the ConversationSidebar.
 *
 * A right-aligned sliding panel that contains the conversation interface:
 * conversation selector, message list with streaming support, input area,
 * and pending cascade banner.
 */
import styled, { css, keyframes } from "styled-components";

// ── Animations ─────────────────────────────────────────────────────────

const slideIn = keyframes`
  from { transform: translateX(100%); }
  to   { transform: translateX(0); }
`;

const slideOut = keyframes`
  from { transform: translateX(0); }
  to   { transform: translateX(100%); }
`;

const pulse = keyframes`
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
`;

const blink = keyframes`
  0%, 50% { opacity: 1; }
  51%, 100% { opacity: 0; }
`;

// ── Overlay ────────────────────────────────────────────────────────────

export const SidebarOverlay = styled.div<{ $closing?: boolean }>`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.3);
  z-index: ${({ theme }) => theme.zIndices.sticky + 50};
  opacity: ${({ $closing }) => ($closing ? 0 : 1)};
  transition: opacity 0.2s ease;
`;

// ── Sidebar Container ──────────────────────────────────────────────────

export const SidebarContainer = styled.aside<{ $closing?: boolean }>`
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 450px;
  max-width: 100vw;
  z-index: ${({ theme }) => theme.zIndices.sticky + 51};
  background: ${({ theme }) => theme.colors.bg.elevated};
  border-left: 1px solid ${({ theme }) => theme.colors.border.default};
  display: flex;
  flex-direction: column;
  box-shadow: ${({ theme }) => theme.shadows.lg};

  ${({ $closing }) =>
    $closing
      ? css`
          animation: ${slideOut} 0.2s ease-out forwards;
        `
      : css`
          animation: ${slideIn} 0.25s ease-out;
        `}
`;

// ── Header ─────────────────────────────────────────────────────────────

export const SidebarHeader = styled.header`
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border.subtle};
  flex-shrink: 0;
`;

export const SidebarTitle = styled.h2`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.base};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text.primary};
  margin: 0;
`;

// ── Conversation Selector ──────────────────────────────────────────────

export const SelectorContainer = styled.div`
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
  border-bottom: 1px solid ${({ theme }) => theme.colors.border.subtle};
  flex-shrink: 0;
`;

export const SelectorDropdown = styled.select`
  width: 100%;
  padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.primary};
  background: ${({ theme }) => theme.colors.bg.primary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.md};
  cursor: pointer;
  outline: none;

  &:focus {
    border-color: ${({ theme }) => theme.colors.accent.blue};
    box-shadow: 0 0 0 2px ${({ theme }) => theme.colors.status.active.bg};
  }
`;

export const NewConversationButton = styled.button`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.xs};
  margin-top: ${({ theme }) => theme.spacing.sm};
  padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
  width: 100%;
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  font-weight: 500;
  color: ${({ theme }) => theme.colors.accent.blue};
  background: transparent;
  border: 1px dashed ${({ theme }) => theme.colors.accent.blue};
  border-radius: ${({ theme }) => theme.radii.md};
  cursor: pointer;
  transition: background ${({ theme }) => theme.transitions.fast};

  &:hover {
    background: ${({ theme }) => theme.colors.status.active.bg};
  }
`;

// ── Message List ───────────────────────────────────────────────────────

export const MessageListContainer = styled.div`
  flex: 1;
  overflow-y: auto;
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.md};
`;

export const MessageBubble = styled.div<{ $role: "user" | "assistant" }>`
  max-width: 90%;
  padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
  border-radius: ${({ theme }) => theme.radii.lg};
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  line-height: 1.5;
  word-break: break-word;

  ${({ $role, theme }) =>
    $role === "user"
      ? css`
          align-self: flex-end;
          background: ${theme.colors.accent.blue};
          color: #ffffff;
          border-bottom-right-radius: ${theme.radii.sm};
        `
      : css`
          align-self: flex-start;
          background: ${theme.colors.bg.tertiary};
          color: ${theme.colors.text.primary};
          border-bottom-left-radius: ${theme.radii.sm};
        `}
`;

export const MessageMeta = styled.div<{ $role: "user" | "assistant" }>`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
  margin-top: ${({ theme }) => theme.spacing.xs};
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.text.muted};

  ${({ $role }) =>
    $role === "user"
      ? css`
          justify-content: flex-end;
        `
      : css`
          justify-content: flex-start;
        `}
`;

export const FilesEditedBadge = styled.span`
  display: inline-flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.xs};
  padding: 2px ${({ theme }) => theme.spacing.xs};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  background: ${({ theme }) => theme.colors.status.success.bg};
  color: ${({ theme }) => theme.colors.status.success.text};
  border-radius: ${({ theme }) => theme.radii.sm};
`;

export const MessageWrapper = styled.div<{ $role: "user" | "assistant" }>`
  display: flex;
  flex-direction: column;
  align-items: ${({ $role }) => ($role === "user" ? "flex-end" : "flex-start")};
`;

// ── Streaming Indicator ────────────────────────────────────────────────

export const StreamingBubble = styled(MessageBubble)`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.xs};
`;

export const StreamingCursor = styled.span`
  display: inline-block;
  width: 8px;
  height: 14px;
  margin-left: 2px;
  background: ${({ theme }) => theme.colors.text.primary};
  animation: ${blink} 0.8s step-end infinite;
  vertical-align: text-bottom;
`;

export const TypingIndicator = styled.div`
  display: flex;
  align-items: center;
  gap: 4px;
  padding: ${({ theme }) => theme.spacing.sm};
`;

export const TypingDot = styled.span<{ $delay?: number }>`
  width: 6px;
  height: 6px;
  background: ${({ theme }) => theme.colors.text.muted};
  border-radius: 50%;
  animation: ${pulse} 1.2s ease-in-out infinite;
  animation-delay: ${({ $delay }) => $delay || 0}ms;
`;

// ── Input Area ─────────────────────────────────────────────────────────

export const InputContainer = styled.div`
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
  border-top: 1px solid ${({ theme }) => theme.colors.border.subtle};
  flex-shrink: 0;
`;

export const InputWrapper = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.sm};
`;

export const InputTextarea = styled.textarea<{ $disabled?: boolean }>`
  width: 100%;
  min-height: 60px;
  max-height: 150px;
  padding: ${({ theme }) => theme.spacing.sm} ${({ theme }) => theme.spacing.md};
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.primary};
  background: ${({ theme }) => theme.colors.bg.primary};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.md};
  resize: vertical;
  outline: none;
  line-height: 1.5;

  &::placeholder {
    color: ${({ theme }) => theme.colors.text.muted};
  }

  &:focus {
    border-color: ${({ theme }) => theme.colors.accent.blue};
    box-shadow: 0 0 0 2px ${({ theme }) => theme.colors.status.active.bg};
  }

  &:disabled {
    opacity: 0.6;
    cursor: not-allowed;
    background: ${({ theme }) => theme.colors.bg.secondary};
  }
`;

export const InputActions = styled.div`
  display: flex;
  align-items: center;
  justify-content: space-between;
`;

export const InputHint = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.text.muted};
`;

// ── Pending Cascade Banner ─────────────────────────────────────────────

export const CascadeBanner = styled.div`
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.sm};
  padding: ${({ theme }) => theme.spacing.md} ${({ theme }) => theme.spacing.lg};
  background: ${({ theme }) => theme.colors.status.warning.bg};
  border-top: 1px solid ${({ theme }) => theme.colors.status.warning.border};
  flex-shrink: 0;
`;

export const CascadeBannerTitle = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.status.warning.text};
`;

export const CascadeBannerText = styled.p`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.secondary};
`;

export const CascadeBannerActions = styled.div`
  display: flex;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.sm};
`;

// ── Loading & Error States ─────────────────────────────────────────────

export const LoadingContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: ${({ theme }) => theme.spacing.xxl};
  color: ${({ theme }) => theme.colors.text.muted};
`;

export const LoadingSpinner = styled.div`
  width: 24px;
  height: 24px;
  border: 2px solid ${({ theme }) => theme.colors.border.default};
  border-top-color: ${({ theme }) => theme.colors.accent.blue};
  border-radius: 50%;
  animation: spin 0.8s linear infinite;

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
`;

export const LoadingText = styled.span`
  margin-top: ${({ theme }) => theme.spacing.md};
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
`;

export const ErrorContainer = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: ${({ theme }) => theme.spacing.md};
  padding: ${({ theme }) => theme.spacing.xl};
  text-align: center;
`;

export const ErrorText = styled.p`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.status.error.text};
`;

// ── Empty State ────────────────────────────────────────────────────────

export const EmptyState = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: ${({ theme }) => theme.spacing.xxl};
  text-align: center;
  flex: 1;
`;

export const EmptyStateText = styled.p`
  margin: 0;
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.muted};
  line-height: 1.5;
`;

export const EmptyStateHint = styled.p`
  margin: ${({ theme }) => theme.spacing.sm} 0 0;
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.xs};
  color: ${({ theme }) => theme.colors.text.muted};
`;

// ── Message Content (with markdown support) ────────────────────────────

export const MessageContent = styled.div`
  /* Basic formatting for message content */
  p {
    margin: 0;
  }

  p + p {
    margin-top: ${({ theme }) => theme.spacing.sm};
  }

  code {
    font-family: ${({ theme }) => theme.fonts.mono};
    font-size: 0.9em;
    padding: 1px 4px;
    background: rgba(0, 0, 0, 0.1);
    border-radius: ${({ theme }) => theme.radii.sm};
  }

  pre {
    margin: ${({ theme }) => theme.spacing.sm} 0;
    padding: ${({ theme }) => theme.spacing.sm};
    background: ${({ theme }) => theme.colors.bg.primary};
    border-radius: ${({ theme }) => theme.radii.md};
    overflow-x: auto;

    code {
      padding: 0;
      background: none;
    }
  }

  ul,
  ol {
    margin: ${({ theme }) => theme.spacing.sm} 0;
    padding-left: ${({ theme }) => theme.spacing.lg};
  }

  li {
    margin: ${({ theme }) => theme.spacing.xs} 0;
  }
`;
