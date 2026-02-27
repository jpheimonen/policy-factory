/**
 * Item Detail page (placeholder).
 *
 * Route: /layers/:layerSlug/:itemSlug
 * Real content added in step 011.
 */
import { useParams } from "react-router-dom";
import { useTranslation } from "@/i18n/index.ts";
import { Text } from "@/components/atoms/index.ts";
import { PageWrapper } from "./ItemDetailPage.styles.ts";

export function ItemDetailPage() {
  const { t } = useTranslation();
  const { slug, item } = useParams<{ slug: string; item: string }>();

  return (
    <PageWrapper>
      <Text as="h1" $variant="heading" $size="xl">
        {t("items.title")}
      </Text>
      <Text $variant="muted" $size="md">
        {slug} / {item}
      </Text>
      <Text $variant="muted" $size="sm">
        {t("common.comingSoon")}
      </Text>
    </PageWrapper>
  );
}
