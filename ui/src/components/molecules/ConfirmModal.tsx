/**
 * ConfirmModal molecule.
 *
 * A modal overlay with title, message, and confirm/cancel buttons.
 * Supports variants: default, warning, danger — affecting the confirm
 * button's colour to indicate the severity of the action.
 *
 * Keyboard support: Escape cancels, Enter confirms.
 * Used for: discard-unsaved-changes, delete-item, and other
 * confirmation dialogs throughout the app.
 *
 * Follows the cc-runner ConfirmModal.tsx pattern.
 */
import { useEffect, useCallback } from "react";
import styled, { css } from "styled-components";
import { Button } from "@/components/atoms/index.ts";

type ConfirmVariant = "default" | "warning" | "danger";

export interface ConfirmModalProps {
  /** Whether the modal is visible */
  isOpen: boolean;
  /** Called when the user confirms the action */
  onConfirm: () => void;
  /** Called when the user cancels (Escape, overlay click, or Cancel button) */
  onCancel: () => void;
  /** Modal title */
  title: string;
  /** Descriptive message explaining the action */
  message: string;
  /** Label for the confirm button */
  confirmLabel?: string;
  /** Label for the cancel button */
  cancelLabel?: string;
  /** Affects confirm button styling: danger = red/destructive */
  variant?: ConfirmVariant;
  /** Show loading state on the confirm button */
  loading?: boolean;
}

// ── Styled components ──────────────────────────────────────────────

const Overlay = styled.div`
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: ${({ theme }) => theme.zIndices.modal};
  padding: ${({ theme }) => theme.spacing.lg};
`;

const Content = styled.div`
  background: ${({ theme }) => theme.colors.bg.elevated};
  border: 1px solid ${({ theme }) => theme.colors.border.default};
  border-radius: ${({ theme }) => theme.radii.lg};
  box-shadow: ${({ theme }) => theme.shadows.lg};
  max-width: 440px;
  width: 100%;
  padding: ${({ theme }) => theme.spacing.xl};
  display: flex;
  flex-direction: column;
  gap: ${({ theme }) => theme.spacing.lg};
`;

const Title = styled.h3`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.lg};
  font-weight: 600;
  color: ${({ theme }) => theme.colors.text.primary};
  margin: 0;
`;

const Message = styled.p`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.md};
  color: ${({ theme }) => theme.colors.text.secondary};
  line-height: 1.6;
  margin: 0;
`;

const Actions = styled.div`
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: ${({ theme }) => theme.spacing.sm};
`;

const ConfirmButton = styled(Button)<{ $confirmVariant: ConfirmVariant }>`
  ${({ $confirmVariant, theme }) =>
    $confirmVariant === "danger" &&
    css`
      background: ${theme.colors.accent.red};
      color: #ffffff;

      &:hover:not(:disabled) {
        opacity: 0.9;
      }
    `}

  ${({ $confirmVariant, theme }) =>
    $confirmVariant === "warning" &&
    css`
      background: ${theme.colors.accent.yellow};
      color: #ffffff;

      &:hover:not(:disabled) {
        opacity: 0.9;
      }
    `}
`;

// ── Component ──────────────────────────────────────────────────────

export function ConfirmModal({
  isOpen,
  onConfirm,
  onCancel,
  title,
  message,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "default",
  loading = false,
}: ConfirmModalProps) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCancel();
      } else if (e.key === "Enter") {
        onConfirm();
      }
    },
    [onCancel, onConfirm],
  );

  useEffect(() => {
    if (isOpen) {
      document.addEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "hidden";
    }
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = "";
    };
  }, [isOpen, handleKeyDown]);

  if (!isOpen) return null;

  return (
    <Overlay role="dialog" aria-modal="true" onClick={onCancel}>
      <Content
        role="document"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={(e) => e.stopPropagation()}
      >
        <Title>{title}</Title>
        <Message>{message}</Message>
        <Actions>
          <Button $variant="secondary" $size="sm" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <ConfirmButton
            $variant={variant === "danger" ? "danger" : "primary"}
            $confirmVariant={variant}
            $size="sm"
            $loading={loading}
            onClick={onConfirm}
            disabled={loading}
          >
            {confirmLabel}
          </ConfirmButton>
        </Actions>
      </Content>
    </Overlay>
  );
}
