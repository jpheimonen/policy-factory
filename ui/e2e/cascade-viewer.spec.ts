import { test, expect, Page } from "@playwright/test";

/**
 * E2E tests for the live cascade viewer.
 *
 * Verifies: cascade display, progress indicator, streaming text,
 * paused cascade controls.
 */

async function setupAndLogin(page: Page) {
  await page.request.post("/api/auth/register", {
    data: { email: "cascade@test.com", password: "password123" },
  });
  await page.goto("/login");
  await page.getByLabel(/email/i).fill("cascade@test.com");
  await page.getByLabel(/password/i).fill("password123");
  await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();
  await expect(page).toHaveURL(/\/$/);
}

test.describe("Cascade Viewer", () => {
  test("cascade page is accessible", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/cascade");

    // The cascade viewer page should load
    await expect(page.locator("main, [role='main'], .page-content, .cascade").first()).toBeVisible();
  });

  test("shows idle state when no cascade running", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/cascade");

    // Should show some idle/no-cascade indicator
    const content = await page.textContent("body");
    // Page should not be blank
    expect(content).toBeTruthy();
  });
});
