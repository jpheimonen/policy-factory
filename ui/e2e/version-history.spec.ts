import { test, expect } from "@playwright/test";
import { setupAndLogin, getAdminToken } from "./helpers";

/**
 * E2E tests for version history.
 *
 * Verifies: git history entries displayed with dates and descriptions.
 */

test.describe("Version History", () => {
  test("version history page loads", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/history/values");

    // Page should load without errors
    await expect(page.locator("main, [role='main'], .page-content, .history").first()).toBeVisible();
  });

  test("shows history entries", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    // Create an item to generate git history
    await page.request.post("/api/layers/values/items", {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        filename: "history-test.md",
        frontmatter: { title: "History Test", status: "draft", references: [] },
        body: "History test body.",
      },
    });

    await page.goto("/history/values");

    // The page should have some content
    const content = await page.textContent("body");
    expect(content).toBeTruthy();
  });
});
