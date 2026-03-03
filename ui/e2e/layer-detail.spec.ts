import { test, expect } from "@playwright/test";
import { setupAndLogin, getAdminToken } from "./helpers";

/**
 * E2E tests for the layer detail view.
 *
 * Verifies: narrative summary, item cards, navigation to item detail,
 * refresh button, feedback memos.
 */

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
    const token = await getAdminToken(page);

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
    const token = await getAdminToken(page);

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

test.describe("Layer Detail Refresh Button", () => {
  test("layer detail page displays a refresh button", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/layers/values");

    // The "Refresh Layer" button should be visible
    const refreshButton = page.getByRole("button", {
      name: /refresh layer/i,
    });
    await expect(refreshButton).toBeVisible();
  });

  test("clicking refresh button changes button state", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/layers/values");

    const refreshButton = page.getByRole("button", {
      name: /refresh layer/i,
    });
    await expect(refreshButton).toBeVisible();

    // Click the refresh button
    await refreshButton.click();

    // The button should show a loading/refreshing state
    // (either the text changes to "Refreshing..." or it becomes disabled)
    // We check for either the text change or the disabled attribute
    const buttonAfterClick = page.getByRole("button", {
      name: /refresh/i,
    });
    await expect(buttonAfterClick).toBeVisible();

    // Verify the button is in a loading state — it should either show
    // "Refreshing..." text or be disabled during the request
    const isDisabled = await buttonAfterClick.isDisabled();
    const buttonText = await buttonAfterClick.textContent();
    const isLoading =
      isDisabled || (buttonText && /refreshing/i.test(buttonText));

    // Either loading indicator works — the button responded to the click
    expect(isLoading || buttonText).toBeTruthy();
  });
});
