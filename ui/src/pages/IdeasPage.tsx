/**
 * Ideas page (placeholder).
 *
 * Route: /ideas
 * Real content added in step 021.
 */
import { useTranslation } from "@/i18n/index.ts";
import { Text } from "@/components/atoms/index.ts";
import { PageWrapper } from "./IdeasPage.styles.ts";

export function IdeasPage() {
  const { t } = useTranslation();

  return (
    <PageWrapper>
      <Text as="h1" $variant="heading" $size="xl">
        {t("nav.ideas")}
      </Text>
      <Text $variant="muted" $size="md">
        {t("common.comingSoon")}
      </Text>
    </PageWrapper>
  );
}
