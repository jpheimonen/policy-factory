/**
 * Placeholder page component.
 *
 * Used for routes whose real pages are not yet built.
 * Displays the page name in a centered layout.
 */
import styled from "styled-components";
import { Text } from "@/components/atoms/index.ts";
import { useTranslation } from "@/i18n/index.ts";

const Wrapper = styled.div`
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 40vh;
  gap: ${({ theme }) => theme.spacing.md};
`;

interface PlaceholderPageProps {
  /** i18n key for the page title. */
  titleKey: string;
}

export function PlaceholderPage({ titleKey }: PlaceholderPageProps) {
  const { t } = useTranslation();

  return (
    <Wrapper>
      <Text as="h1" $variant="heading" $size="xl">
        {t(titleKey)}
      </Text>
      <Text $variant="muted" $size="md">
        {t("common.comingSoon")}
      </Text>
    </Wrapper>
  );
}
