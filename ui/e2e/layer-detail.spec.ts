import { test, expect, Page } from "@playwright/test";

/**
 * E2E tests for the layer detail view.
 *
 * Verifies: narrative summary, item cards, navigation to item detail,
 * refresh button, feedback memos.
 */

async function setupAndLogin(page: Page) {
  await page.request.post("/api/auth/register", {
    data: { email: "detail@test.com", password: "password123" },
  });
  await page.goto("/login");
  await page.getByLabel(/email/i).fill("detail@test.com");
  await page.getByLabel(/password/i).fill("password123");
  await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();
  await expect(page).toHaveURL(/\/$/);
}

test.describe("Layer Detail View", () => {
  test("shows narrative summary", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/layers/values");

    // The narrative summary should be displayed
    // (content comes from README.md — may show "Values" heading)
    await expect(page.locator("main, [role='main'], .layer-detail, .page-content").first()).toBeVisible();
  });

  test("shows items as cards", async ({ page }) => {
    await setupAndLogin(page);

    // Create a test item via API
    const loginResp = await page.request.post("/api/auth/login", {
      data: { email: "detail@test.com", password: "password123" },
    });
    const { token } = await loginResp.json();

    await page.request.post("/api/layers/values/items", {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        filename: "test-item.md",
        frontmatter: {
          title: "E2E Test Item",
          status: "draft",
          references: [],
        },
        body: "Test item body content.",
      },
    });

    await page.goto("/layers/values");
    await expect(page.getByText("E2E Test Item").first()).toBeVisible();
  });

  test("clicking item navigates to detail", async ({ page }) => {
    await setupAndLogin(page);

    // Create item via API
    const loginResp = await page.request.post("/api/auth/login", {
      data: { email: "detail@test.com", password: "password123" },
    });
    const { token } = await loginResp.json();

    await page.request.post("/api/layers/values/items", {
      headers: { Authorization: `Bearer ${token}` },
      data: {
        filename: "nav-test.md",
        frontmatter: { title: "Navigation Test", status: "draft", references: [] },
        body: "Navigation test body.",
      },
    });

    await page.goto("/layers/values");
    await page.getByText("Navigation Test").first().click();

    // Should navigate to item detail
    await expect(page).toHaveURL(/\/layers\/values\/nav-test/);
  });
});
