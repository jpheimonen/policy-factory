/**
 * History page (placeholder).
 *
 * Route: /history/:layerSlug
 * Real content added in step 022.
 */
import { useParams } from "react-router-dom";
import { useTranslation } from "@/i18n/index.ts";
import { Text } from "@/components/atoms/index.ts";
import { PageWrapper } from "./HistoryPage.styles.ts";

export function HistoryPage() {
  const { t } = useTranslation();
  const { slug } = useParams<{ slug: string }>();

  return (
    <PageWrapper>
      <Text as="h1" $variant="heading" $size="xl">
        {t("history.title")}
      </Text>
      <Text $variant="muted" $size="md">
        {slug}
      </Text>
      <Text $variant="muted" $size="sm">
        {t("common.comingSoon")}
      </Text>
    </PageWrapper>
  );
}
