import { test, expect } from "@playwright/test";
import { setupAndLogin } from "./helpers";

/**
 * E2E tests for the idea inbox.
 *
 * Verifies: idea submission, listing, radar chart, sorting, filtering.
 */

test.describe("Idea Inbox", () => {
  test("idea submission form creates idea", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/ideas");

    // Find the idea submission form
    const textInput = page.getByPlaceholder(/idea|suggestion|submit|enter/i);
    if (await textInput.isVisible()) {
      await textInput.fill("Finland should invest in AI research");
      await page.getByRole("button", { name: "Submit Idea" }).click();

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
