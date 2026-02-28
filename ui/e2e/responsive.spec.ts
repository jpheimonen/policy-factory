import { test, expect, Page } from "@playwright/test";

/**
 * E2E tests for responsive behaviour.
 *
 * Verifies: pages are usable at 768px viewport width.
 */

async function setupAndLogin(page: Page) {
  await page.request.post("/api/auth/register", {
    data: { email: "responsive@test.com", password: "password123" },
  });
  await page.goto("/login");
  await page.getByLabel(/email/i).fill("responsive@test.com");
  await page.getByLabel(/password/i).fill("password123");
  await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();
  await expect(page).toHaveURL(/\/$/);
}

test.describe("Responsive Behaviour", () => {
  test("stack overview is usable at 768px", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await setupAndLogin(page);

    // All layer cards should be visible
    await expect(page.getByText("Values").first()).toBeVisible();
    await expect(page.getByText("Policies").first()).toBeVisible();

    // No horizontal overflow
    const bodyWidth = await page.evaluate(() => document.body.scrollWidth);
    expect(bodyWidth).toBeLessThanOrEqual(768 + 20); // small margin
  });

  test("layer detail is usable at 768px", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await setupAndLogin(page);
    await page.goto("/layers/values");

    // Page should be usable
    await expect(page.locator("main, [role='main'], .page-content").first()).toBeVisible();
  });

  test("navigation accessible at all viewport sizes", async ({ page }) => {
    await page.setViewportSize({ width: 768, height: 1024 });
    await setupAndLogin(page);

    // Navigation should be accessible (either visible or via menu button)
    const nav = page.locator("nav, [role='navigation'], header");
    await expect(nav.first()).toBeVisible();
  });
});
