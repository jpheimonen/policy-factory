/**
 * EmptyState molecule.
 *
 * An icon with a title, optional subtitle, and optional action button.
 * Used when a list or section has no data to display (e.g., no items in a layer).
 *
 * Follows the cc-runner EmptyState pattern.
 */
import styled from "styled-components";
import { Button } from "@/components/atoms/index.ts";

interface EmptyStateProps {
  /** Primary empty-state title (e.g., "No items in this layer yet"). */
  title: string;
  /** Optional secondary description. */
  subtitle?: string;
  /** Optional icon character or emoji to display above the title. */
  icon?: string;
  /** Optional action button label (e.g., "Create Item"). */
  actionLabel?: string;
  /** Callback when the action button is clicked. */
  onAction?: () => void;
  /** If true, renders inline with reduced padding (for sections). */
  compact?: boolean;
}

const Wrapper = styled.div<{ $compact: boolean }>`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: ${({ theme }) => theme.spacing.sm};
  padding: ${({ theme, $compact }) =>
    $compact ? theme.spacing.xl : theme.spacing.xxl};
  min-height: ${({ $compact }) => ($compact ? "auto" : "160px")};
  text-align: center;
`;

const Icon = styled.div`
  font-size: 28px;
  margin-bottom: ${({ theme }) => theme.spacing.xs};
  opacity: 0.6;
`;

const Title = styled.p`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.md};
  font-weight: 500;
  color: ${({ theme }) => theme.colors.text.secondary};
  margin: 0;
`;

const Subtitle = styled.p`
  font-family: ${({ theme }) => theme.fonts.sans};
  font-size: ${({ theme }) => theme.fontSizes.sm};
  color: ${({ theme }) => theme.colors.text.muted};
  margin: 0;
  max-width: 360px;
`;

export function EmptyState({
  title,
  subtitle,
  icon,
  actionLabel,
  onAction,
  compact = false,
}: EmptyStateProps) {
  return (
    <Wrapper $compact={compact}>
      {icon && <Icon>{icon}</Icon>}
      <Title>{title}</Title>
      {subtitle && <Subtitle>{subtitle}</Subtitle>}
      {actionLabel && onAction && (
        <Button $variant="secondary" $size="sm" onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </Wrapper>
  );
}
