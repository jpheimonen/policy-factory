/**
 * Cascade page (placeholder).
 *
 * Route: /cascade
 * Real content added in step 020.
 */
import { useTranslation } from "@/i18n/index.ts";
import { Text } from "@/components/atoms/index.ts";
import { PageWrapper } from "./CascadePage.styles.ts";

export function CascadePage() {
  const { t } = useTranslation();

  return (
    <PageWrapper>
      <Text as="h1" $variant="heading" $size="xl">
        {t("nav.cascade")}
      </Text>
      <Text $variant="muted" $size="md">
        {t("common.comingSoon")}
      </Text>
    </PageWrapper>
  );
}
