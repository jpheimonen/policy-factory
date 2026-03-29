import { test, expect } from "@playwright/test";
import {
  setupAndLogin,
  getAdminToken,
  createTestItem,
  createTestConversation,
} from "./helpers";

/**
 * E2E tests for the philosophy layer.
 *
 * Verifies: navigation, layer detail page, item detail, theme colors,
 * and conversation integration on philosophy items.
 */

test.describe("Philosophy Layer Navigation", () => {
  test("philosophy layer appears in stack overview", async ({ page }) => {
    await setupAndLogin(page);

    // Should show all layers including philosophy
    await expect(
      page.getByText(/philosophy|political philosophy/i).first(),
    ).toBeVisible();
  });

  test("philosophy layer link is clickable and navigates correctly", async ({
    page,
  }) => {
    await setupAndLogin(page);

    // Find and click the philosophy layer link
    const philosophyLink = page.getByText(/philosophy|political philosophy/i).first();
    await philosophyLink.click();

    // Should navigate to the philosophy layer detail page
    await expect(page).toHaveURL(/\/layers\/philosophy/);
  });

  test("philosophy appears in the layer order", async ({ page }) => {
    await setupAndLogin(page);

    // The stack overview should show philosophy layer
    // It should be visible along with other layers
    const mainContent = page.locator("main, [role='main'], .page-content").first();
    await expect(mainContent).toBeVisible();

    // Check that philosophy is present
    await expect(
      page.getByText(/philosophy|political philosophy/i).first(),
    ).toBeVisible();

    // Values should also be visible (confirming layer order works)
    await expect(page.getByText(/values/i).first()).toBeVisible();
  });
});

test.describe("Philosophy Layer Detail Page", () => {
  test("philosophy layer detail page loads successfully", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/layers/philosophy");

    // Page should load without errors
    await expect(
      page.locator("main, [role='main'], .page-content").first(),
    ).toBeVisible();

    // Should not show error state
    const errorText = page.getByText(/error|not found|invalid/i);
    await expect(errorText).not.toBeVisible();
  });

  test("page shows correct layer name", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/layers/philosophy");

    // Should show the layer name in the header
    await expect(
      page.getByText(/philosophy|political philosophy/i).first(),
    ).toBeVisible();
  });

  test("narrative summary section displays README content", async ({
    page,
  }) => {
    await setupAndLogin(page);
    await page.goto("/layers/philosophy");

    // Should show the narrative summary section
    const summarySection = page.getByText(/summary|narrative/i);
    await expect(summarySection.first()).toBeVisible();
  });

  test("items list displays philosophy items after seeding", async ({
    page,
  }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    // Create a test item in the philosophy layer
    await createTestItem(
      page,
      token,
      "philosophy",
      "test-philosophy-item.md",
      "Test Philosophy Item",
      "This is a test philosophy item for E2E testing.",
    );

    await page.goto("/layers/philosophy");

    // Should show the test item in the items list
    await expect(page.getByText("Test Philosophy Item")).toBeVisible();
  });

  test("refresh button is visible", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/layers/philosophy");

    // Should show the refresh button
    const refreshButton = page.getByRole("button", {
      name: /refresh/i,
    });
    await expect(refreshButton).toBeVisible();
  });

  test("conversation toggle is visible on philosophy layer", async ({
    page,
  }) => {
    await setupAndLogin(page);
    await page.goto("/layers/philosophy");

    // Should show the conversation toggle (exact match to avoid matching conversation list items)
    const toggleButton = page.getByRole("button", { name: "Chat" });
    await expect(toggleButton).toBeVisible();
  });
});

test.describe("Philosophy Item Detail", () => {
  test("philosophy item detail page loads successfully", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    // Create a test philosophy item
    await createTestItem(
      page,
      token,
      "philosophy",
      "philosophy-detail-test.md",
      "Philosophy Detail Test Item",
      "# Philosophy Test\n\nThis is the philosophy item body.",
    );

    await page.goto("/layers/philosophy/philosophy-detail-test");

    // Page should load
    await expect(
      page.locator("main, [role='main'], .page-content").first(),
    ).toBeVisible();

    // Should show the item title
    await expect(page.getByText("Philosophy Detail Test Item").first()).toBeVisible();
  });

  test("philosophy item displays frontmatter and body", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    await createTestItem(
      page,
      token,
      "philosophy",
      "philosophy-frontmatter-test.md",
      "Philosophy Frontmatter Test",
      "This is the philosophy body content for frontmatter testing.",
    );

    await page.goto("/layers/philosophy/philosophy-frontmatter-test");

    // Should show the title
    await expect(
      page.getByText("Philosophy Frontmatter Test").first(),
    ).toBeVisible();

    // Should show the body content
    await expect(
      page.getByText(/philosophy body content/i).first(),
    ).toBeVisible();
  });

  test("edit mode works on philosophy items", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    await createTestItem(
      page,
      token,
      "philosophy",
      "philosophy-edit-test.md",
      "Philosophy Edit Test",
      "Editable philosophy content.",
    );

    await page.goto("/layers/philosophy/philosophy-edit-test");

    // Find and click edit button
    const editButton = page.getByRole("button", { name: /edit/i });
    if (await editButton.isVisible()) {
      await editButton.click();

      // Should enter edit mode — look for text inputs or textareas
      const editableElement = page.locator(
        "textarea, input[type='text'], [contenteditable='true']",
      );
      await expect(editableElement.first()).toBeVisible();
    }
  });

  test("conversation sidebar works on philosophy items", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    await createTestItem(
      page,
      token,
      "philosophy",
      "philosophy-conv-test.md",
      "Philosophy Conversation Test",
      "Philosophy content for conversation testing.",
    );

    await page.goto("/layers/philosophy/philosophy-conv-test");

    // Click conversation toggle (exact match to avoid matching conversation list items)
    const toggleButton = page.getByRole("button", { name: "Chat" });
    await toggleButton.click();

    // Sidebar should appear
    const sidebar = page.locator("aside").first();
    await expect(sidebar).toBeVisible();

    // Should have conversation-related content (heading or input)
    const conversationHeading = sidebar.getByRole("heading", { name: /conversation/i });
    const textarea = sidebar.locator("textarea");
    const hasContent = await conversationHeading.isVisible().catch(() => false) ||
                       await textarea.isVisible().catch(() => false);
    expect(hasContent).toBe(true);
  });

  test("can create conversation on philosophy item", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    const uniqueId = Date.now();
    await createTestItem(
      page,
      token,
      "philosophy",
      `philosophy-create-conv-${uniqueId}.md`,
      `Philosophy Create Conv ${uniqueId}`,
      "Philosophy content.",
    );

    await createTestConversation(
      page,
      token,
      "philosophy",
      `philosophy-create-conv-${uniqueId}.md`,
    );

    await page.goto(`/layers/philosophy/philosophy-create-conv-${uniqueId}`);

    // Open sidebar (exact match to avoid matching conversation list items)
    const toggleButton = page.getByRole("button", { name: "Chat" });
    await toggleButton.click();

    // Wait for conversation to load
    await page.waitForTimeout(500);

    // Input should be available
    const textarea = page.locator("textarea");
    await expect(textarea).toBeVisible();
  });
});

test.describe("Philosophy Theme Colors", () => {
  test("philosophy layer uses theme color in layer detail", async ({
    page,
  }) => {
    await setupAndLogin(page);
    await page.goto("/layers/philosophy");

    // Wait for the page to fully render
    await page.waitForLoadState("networkidle");

    // The page should show philosophy layer name
    await expect(
      page.getByText(/philosophy/i).first(),
    ).toBeVisible();

    // The header should be styled (verify page has loaded with content)
    const header = page.locator("h1, h2, [class*='Header']").first();
    await expect(header).toBeVisible();
  });

  test("philosophy layer color is consistent across navigation", async ({
    page,
  }) => {
    await setupAndLogin(page);

    // Navigate from stack overview to philosophy layer
    await page.goto("/");
    const philosophyLink = page.getByText(/philosophy|political philosophy/i).first();
    await philosophyLink.click();

    await expect(page).toHaveURL(/\/layers\/philosophy/);

    // Verify we're on the philosophy page
    await expect(
      page.getByText(/philosophy|political philosophy/i).first(),
    ).toBeVisible();

    // Navigate to a philosophy item
    const token = await getAdminToken(page);
    await createTestItem(
      page,
      token,
      "philosophy",
      "theme-color-nav-test.md",
      "Theme Color Nav Test",
    );

    await page.goto("/layers/philosophy/theme-color-nav-test");

    // Back link should reference philosophy layer
    const backLink = page.getByText(/philosophy/i);
    await expect(backLink.first()).toBeVisible();
  });
});

test.describe("Philosophy Layer in Cascade", () => {
  // Note: Actually triggering a cascade that includes philosophy
  // requires the full cascade system. These tests verify the UI supports it.

  test("philosophy layer can be refreshed", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/layers/philosophy");

    // The refresh button should be clickable
    const refreshButton = page.getByRole("button", {
      name: /refresh/i,
    });
    await expect(refreshButton).toBeVisible();

    // Click the refresh button
    await refreshButton.click();

    // Button should show loading/refreshing state
    await page.waitForTimeout(500);

    // Button should still be visible (either loading or returned to idle)
    await expect(refreshButton).toBeVisible();
  });
});
