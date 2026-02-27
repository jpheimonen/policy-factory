/**
 * Layer Detail page (placeholder).
 *
 * Route: /layers/:layerSlug
 * Real content added in step 010.
 */
import { useParams } from "react-router-dom";
import { useTranslation } from "@/i18n/index.ts";
import { Text } from "@/components/atoms/index.ts";
import { PageWrapper } from "./LayerDetailPage.styles.ts";

export function LayerDetailPage() {
  const { t } = useTranslation();
  const { slug } = useParams<{ slug: string }>();

  return (
    <PageWrapper>
      <Text as="h1" $variant="heading" $size="xl">
        {t("layers.narrativeSummary")}
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
