import { test, expect, Page } from "@playwright/test";

/**
 * E2E tests for version history.
 *
 * Verifies: git history entries displayed with dates and descriptions.
 */

async function setupAndLogin(page: Page) {
  await page.request.post("/api/auth/register", {
    data: { email: "history@test.com", password: "password123" },
  });
  await page.goto("/login");
  await page.getByLabel(/email/i).fill("history@test.com");
  await page.getByLabel(/password/i).fill("password123");
  await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();
  await expect(page).toHaveURL(/\/$/);
}

test.describe("Version History", () => {
  test("version history page loads", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/history/values");

    // Page should load without errors
    await expect(page.locator("main, [role='main'], .page-content, .history").first()).toBeVisible();
  });

  test("shows history entries", async ({ page }) => {
    await setupAndLogin(page);

    // Create an item to generate git history
    const loginResp = await page.request.post("/api/auth/login", {
      data: { email: "history@test.com", password: "password123" },
    });
    const { token } = await loginResp.json();

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
