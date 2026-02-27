/**
 * Admin page (placeholder).
 *
 * Route: /admin
 * Real content added in step 023.
 */
import { useTranslation } from "@/i18n/index.ts";
import { Text } from "@/components/atoms/index.ts";
import { PageWrapper } from "./AdminPage.styles.ts";

export function AdminPage() {
  const { t } = useTranslation();

  return (
    <PageWrapper>
      <Text as="h1" $variant="heading" $size="xl">
        {t("admin.title")}
      </Text>
      <Text $variant="muted" $size="md">
        {t("common.comingSoon")}
      </Text>
    </PageWrapper>
  );
}
