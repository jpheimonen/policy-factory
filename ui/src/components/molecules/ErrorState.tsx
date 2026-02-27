/**
 * ErrorState molecule.
 *
 * An error icon with a message and optional retry button.
 * Used at page level when a fetch fails, or inline with `compact`.
 *
 * Follows the cc-runner ErrorState pattern.
 */
import styled from "styled-components";
import { Button } from "@/components/atoms/index.ts";
import { useTranslation } from "@/i18n/index.ts";

interface ErrorStateProps {
  /** The error message to display. Falls back to a generic error string. */
  message?: string;
  /** Callback for the retry button. If omitted, no retry button is shown. */
  onRetry?: () => void;
  /** If true, renders inline with reduced padding (for sections). */
  compact?: boolean;
}

const Wrapper = styled.div<{ $compact: boolean }>`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: ${({ theme }) => theme.spacing.md};
  padding: ${({ theme, $compact }) =>
    $compact ? theme.spacing.xl : theme.spacing.xxl};
  min-height: ${({ $compact }) => ($compact ? "auto" : "200px")};
  text-align: center;
`;

const ErrorIcon = styled.div`
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: ${({ theme }) => theme.colors.status.error.bg};
  display: flex;
  align-items: center;
  justify-content: center;
  color: ${({ theme }) => theme.colors.status.error.text};
  font-size: 20px;
  font-weight: 600;
`;

const ErrorMessage = styled.p`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.secondary};
  margin: 0;
  max-width: 400px;
`;

export function ErrorState({ message, onRetry, compact = false }: ErrorStateProps) {
  const { t } = useTranslation();

  return (
    <Wrapper $compact={compact}>
      <ErrorIcon>!</ErrorIcon>
      <ErrorMessage>{message ?? t("errors.generic")}</ErrorMessage>
      {onRetry && (
        <Button $variant="secondary" $size="sm" onClick={onRetry}>
          {t("common.refresh")}
        </Button>
      )}
    </Wrapper>
  );
}
