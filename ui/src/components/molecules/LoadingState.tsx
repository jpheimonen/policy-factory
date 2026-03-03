/**
 * LoadingState molecule.
 *
 * A centered spinner with an optional message. Used as a page-level
 * placeholder while data is being fetched, or inline with `compact`.
 *
 * Follows the cc-runner LoadingState pattern.
 */
import styled, { keyframes } from "styled-components";
import { useTranslation } from "@/i18n/index.ts";

interface LoadingStateProps {
  /** Optional message below the spinner. Falls back to "Loading..." */
  message?: string;
  /** If true, renders inline with reduced padding (for sections). */
  compact?: boolean;
}

const spin = keyframes`
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
`;

const Wrapper = styled.div<{ $compact: boolean }>`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: ${({ theme }) => theme.spacing.md};
  padding: ${({ theme, $compact }) =>
    $compact ? theme.spacing.xl : theme.spacing.xxl};
  min-height: ${({ $compact }) => ($compact ? "auto" : "200px")};
`;

const Spinner = styled.div`
  width: 28px;
  height: 28px;
  border: 3px solid ${({ theme }) => theme.colors.border.default};
  border-top-color: ${({ theme }) => theme.colors.accent.blue};
  border-radius: 50%;
  animation: ${spin} 0.8s linear infinite;
`;

const Message = styled.span`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.muted};
`;

export function LoadingState({ message, compact = false }: LoadingStateProps) {
  const { t } = useTranslation();

  return (
    <Wrapper $compact={compact}>
      <Spinner />
      <Message>{message ?? t("common.loading")}</Message>
    </Wrapper>
  );
}
