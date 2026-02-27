/**
 * Activity page (placeholder).
 *
 * Route: /activity
 * Real content added in step 022.
 */
import { useTranslation } from "@/i18n/index.ts";
import { Text } from "@/components/atoms/index.ts";
import { PageWrapper } from "./ActivityPage.styles.ts";

export function ActivityPage() {
  const { t } = useTranslation();

  return (
    <PageWrapper>
      <Text as="h1" $variant="heading" $size="xl">
        {t("activity.title")}
      </Text>
      <Text $variant="muted" $size="md">
        {t("common.comingSoon")}
      </Text>
    </PageWrapper>
  );
}
