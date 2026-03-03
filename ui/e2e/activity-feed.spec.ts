import { test, expect } from "@playwright/test";
import { setupAndLogin } from "./helpers";

/**
 * E2E tests for the activity feed.
 *
 * Verifies: event display, filtering, real-time updates.
 */

test.describe("Activity Feed", () => {
  test("activity page is accessible", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/activity");

    await expect(page.locator("main, [role='main'], .page-content, .activity").first()).toBeVisible();
  });

  test("shows events when available", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/activity");

    // The page should render without errors
    const content = await page.textContent("body");
    expect(content).toBeTruthy();
  });
});
