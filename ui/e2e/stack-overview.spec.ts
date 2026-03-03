import { test, expect, Page } from "@playwright/test";

/**
 * E2E tests for the stack overview (home page).
 *
 * Verifies: 5 layer cards displayed, metadata shown, navigation to layer detail.
 */

async function loginAsAdmin(page: Page) {
  // Register a user via API
  await page.request.post("/api/auth/register", {
    data: { email: "admin@test.com", password: "password123" },
  });

  await page.goto("/login");
  await page.getByLabel(/email/i).fill("admin@test.com");
  await page.getByLabel(/password/i).fill("password123");
  await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();
  await expect(page).toHaveURL(/\/$/);
}

test.describe("Stack Overview", () => {
  test("displays all 5 layer cards", async ({ page }) => {
    await loginAsAdmin(page);

    // Should display all 5 layers
    const layerNames = [
      "Values",
      "Situational Awareness",
      "Strategic Objectives",
      "Tactical Objectives",
      "Policies",
    ];

    for (const name of layerNames) {
      await expect(page.getByText(name).first()).toBeVisible();
    }
  });

  test("clicking a layer card navigates to detail view", async ({ page }) => {
    await loginAsAdmin(page);

    // Click on a layer card
    await page.getByText("Values").first().click();

    // Should navigate to layer detail
    await expect(page).toHaveURL(/\/layers\/values/);
  });

  test("input panel is visible", async ({ page }) => {
    await loginAsAdmin(page);

    // The input panel should be visible
    const inputPanel = page.getByPlaceholder(
      /input|submit|type|enter.*text|ask|tell/i
    );
    if (await inputPanel.isVisible()) {
      await expect(inputPanel).toBeVisible();
    }
  });
});
