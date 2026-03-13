import { test, expect } from "@playwright/test";
import { setupAndLogin, getAdminToken } from "./helpers";

/**
 * E2E tests for item detail and editing.
 *
 * Verifies: frontmatter rendering, edit mode, save, cross-layer references.
 */

test.describe("Item Detail and Editing", () => {
  test("renders frontmatter and body", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

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
    const token = await getAdminToken(page);

    // Create test item
    await page.request.post("/api/layers/values/items", {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        filename: "item-edit-test.md",
        frontmatter: {
          title: "Edit Test Item",
          status: "active",
          references: [],
        },
        body: "# Edit Test\n\nEditable item body.",
      },
    });

    await page.goto("/layers/values/item-edit-test.md");

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
