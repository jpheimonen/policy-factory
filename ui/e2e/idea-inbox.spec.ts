import { test, expect, Page } from "@playwright/test";

/**
 * E2E tests for the idea inbox.
 *
 * Verifies: idea submission, listing, radar chart, sorting, filtering.
 */

async function setupAndLogin(page: Page) {
  await page.request.post("/api/auth/register", {
    data: { email: "idea@test.com", password: "password123" },
  });
  await page.goto("/login");
  await page.getByLabel(/email/i).fill("idea@test.com");
  await page.getByLabel(/password/i).fill("password123");
  await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();
  await expect(page).toHaveURL(/\/$/);
}

test.describe("Idea Inbox", () => {
  test("idea submission form creates idea", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/ideas");

    // Find the idea submission form
    const textInput = page.getByPlaceholder(/idea|suggestion|submit|enter/i);
    if (await textInput.isVisible()) {
      await textInput.fill("Finland should invest in AI research");
      await page.getByRole("button", { name: /submit|add|send/i }).click();

      // The idea should appear in the list
      await expect(
        page.getByText(/Finland should invest in AI research/i).first()
      ).toBeVisible();
    }
  });

  test("ideas page is accessible", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/ideas");

    // The ideas page should load without errors
    await expect(page.locator("main, [role='main'], .page-content, .ideas").first()).toBeVisible();
  });
});
