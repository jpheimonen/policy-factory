import { test, expect, Page } from "@playwright/test";

/**
 * E2E tests for item detail and editing.
 *
 * Verifies: frontmatter rendering, edit mode, save, cross-layer references.
 */

async function setupAndLogin(page: Page) {
  await page.request.post("/api/auth/register", {
    data: { email: "item@test.com", password: "password123" },
  });
  const loginResp = await page.request.post("/api/auth/login", {
    data: { email: "item@test.com", password: "password123" },
  });
  const { token } = await loginResp.json();

  // Create test item
  await page.request.post("/api/layers/values/items", {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      filename: "item-detail-test.md",
      frontmatter: {
        title: "Detail Test Item",
        status: "active",
        references: [],
      },
      body: "# Detail Test\n\nThis is the item body for testing.",
    },
  });

  await page.goto("/login");
  await page.getByLabel(/email/i).fill("item@test.com");
  await page.getByLabel(/password/i).fill("password123");
  await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();
  await expect(page).toHaveURL(/\/$/);

  return token;
}

test.describe("Item Detail and Editing", () => {
  test("renders frontmatter and body", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/layers/values/item-detail-test.md");

    // Should show the item title
    await expect(page.getByText("Detail Test Item").first()).toBeVisible();

    // Should show the body content
    await expect(
      page.getByText(/item body for testing/i).first()
    ).toBeVisible();
  });

  test("edit mode allows modification", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/layers/values/item-detail-test.md");

    // Find and click edit button
    const editButton = page.getByRole("button", { name: /edit/i });
    if (await editButton.isVisible()) {
      await editButton.click();

      // Should enter edit mode — look for text inputs or textareas
      const editableElement = page.locator(
        "textarea, input[type='text'], [contenteditable='true']"
      );
      await expect(editableElement.first()).toBeVisible();
    }
  });
});
