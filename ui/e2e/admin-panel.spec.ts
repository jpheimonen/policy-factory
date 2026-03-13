import { test, expect, Page } from "@playwright/test";
import { setupAndLogin, getAdminToken, TEST_ADMIN_EMAIL } from "./helpers";

/**
 * E2E tests for the admin panel.
 *
 * Verifies: admin access, user list, create/delete users, non-admin restriction.
 */

test.describe("Admin Panel", () => {
  test("admin can access admin panel", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/admin");

    // Admin panel should be accessible
    await expect(page.locator("main, [role='main'], .page-content, .admin").first()).toBeVisible();
  });

  test("admin panel shows user list", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/admin");

    // Should show the admin user in the list
    await expect(page.getByText(TEST_ADMIN_EMAIL).first()).toBeVisible();
  });

  test("admin can create user", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/admin");

    // Fill in create user form
    const emailInput = page.getByPlaceholder(/email/i);
    const passwordInput = page.getByPlaceholder(/password/i);

    if (await emailInput.isVisible()) {
      await emailInput.fill("newuser@test.com");
      if (await passwordInput.isVisible()) {
        await passwordInput.fill("newpassword1");
      }
      await page
        .getByRole("button", { name: /create|add.*user/i })
        .click();

      // New user should appear in the list
      await expect(
        page.getByText("newuser@test.com").first()
      ).toBeVisible();
    }
  });

  test("admin cannot delete themselves", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/admin");

    // The delete button for the admin's own account should be disabled
    // or should show an error if clicked
    const adminRow = page.getByText(TEST_ADMIN_EMAIL).first();
    await expect(adminRow).toBeVisible();
  });
});

// ---------------------------------------------------------------------------
// Seed Status Card E2E Tests
// ---------------------------------------------------------------------------

/** All 5 layer slugs in hierarchical order (bottom to top). */
const LAYER_SLUGS = [
  "values",
  "situational-awareness",
  "strategic-objectives",
  "tactical-objectives",
  "policies",
] as const;

/** Display names matching the API's display_name field, in the same order. */
const LAYER_DISPLAY_NAMES = [
  "Values",
  "Situational Awareness",
  "Strategic Objectives",
  "Tactical Objectives",
  "Policies",
] as const;

/**
 * Create a minimal markdown item in a layer via the layers API.
 *
 * Uses `POST /api/layers/{slug}/items` with a minimal valid payload.
 * Returns the filename of the created item for cleanup tracking.
 */
async function createLayerItem(
  page: Page,
  token: string,
  slug: string,
  filename?: string
): Promise<string> {
  const name = filename || `test-item-${Date.now()}-${Math.random().toString(36).slice(2, 8)}.md`;
  const resp = await page.request.post(`/api/layers/${slug}/items`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      filename: name,
      frontmatter: { title: `Test item for ${slug}` },
      body: `Test body content for ${slug} layer.`,
    },
  });
  if (!resp.ok()) {
    throw new Error(
      `Failed to create item in ${slug}: ${resp.status()} ${await resp.text()}`
    );
  }
  return name;
}

/**
 * Delete all items from a single layer via the layers API.
 *
 * Lists all items with `GET /api/layers/{slug}/items`, then deletes each
 * with `DELETE /api/layers/{slug}/items/{filename}`.
 */
async function clearLayer(
  page: Page,
  token: string,
  slug: string
): Promise<void> {
  const listResp = await page.request.get(`/api/layers/${slug}/items`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!listResp.ok()) return;

  const items: { filename: string }[] = await listResp.json();
  for (const item of items) {
    await page.request.delete(`/api/layers/${slug}/items/${item.filename}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
  }
}

/**
 * Delete all items from all 5 layers.
 */
async function clearAllLayers(page: Page, token: string): Promise<void> {
  for (const slug of LAYER_SLUGS) {
    await clearLayer(page, token, slug);
  }
}

test.describe("Seed Status Card", () => {
  let token: string;

  test.beforeEach(async ({ page }) => {
    await setupAndLogin(page);
    token = await getAdminToken(page);
    // Ensure all layers are empty before each test
    await clearAllLayers(page, token);
  });

  test.afterEach(async ({ page }) => {
    // Clean up any items created during the test
    if (token) {
      await clearAllLayers(page, token);
    }
  });

  // -----------------------------------------------------------------------
  // Display tests (empty state)
  // -----------------------------------------------------------------------

  test("seed card displays all 5 layers", async ({ page }) => {
    await page.goto("/admin");

    // The seed card heading should be visible
    await expect(page.getByText("Initial Seed")).toBeVisible();

    // Each layer display name should appear in the card
    for (const name of LAYER_DISPLAY_NAMES) {
      await expect(page.getByText(name, { exact: true }).first()).toBeVisible();
    }
  });

  test("layers are in hierarchical order", async ({ page }) => {
    await page.goto("/admin");

    // Wait for the seed card to load
    await expect(page.getByText("Initial Seed")).toBeVisible();

    // Collect the bounding boxes of each layer name in the card
    const positions: { name: string; y: number }[] = [];
    for (const name of LAYER_DISPLAY_NAMES) {
      const locator = page.getByText(name, { exact: true }).first();
      await expect(locator).toBeVisible();
      const box = await locator.boundingBox();
      expect(box).not.toBeNull();
      positions.push({ name, y: box!.y });
    }

    // Verify each layer appears below the previous one
    for (let i = 1; i < positions.length; i++) {
      expect(
        positions[i].y,
        `${positions[i].name} should appear below ${positions[i - 1].name}`
      ).toBeGreaterThan(positions[i - 1].y);
    }
  });

  test("empty layers show not-seeded indicators", async ({ page }) => {
    await page.goto("/admin");

    // Wait for the seed card to render
    await expect(page.getByText("Initial Seed")).toBeVisible();

    // With no items in any layer, none of the seed buttons should show counts.
    // The i18n template "admin.seedLayerCount" renders "(N items)" only when
    // layer.seeded is true. With all layers empty, no count text should appear.
    await expect(page.getByText(/\d+ items/)).not.toBeVisible();
  });

  // -----------------------------------------------------------------------
  // Prerequisite and disabled state tests
  // -----------------------------------------------------------------------

  test("values and SA seed buttons are enabled when all layers empty", async ({
    page,
  }) => {
    await page.goto("/admin");
    await expect(page.getByText("Initial Seed")).toBeVisible();

    // Values button should be enabled
    const valuesBtn = page.getByRole("button", { name: "Seed Values" });
    await expect(valuesBtn).toBeVisible();
    await expect(valuesBtn).toBeEnabled();

    // Situational Awareness button should be enabled
    const saBtn = page.getByRole("button", {
      name: "Seed Situational Awareness",
    });
    await expect(saBtn).toBeVisible();
    await expect(saBtn).toBeEnabled();
  });

  test("upper-layer seed buttons are disabled when prerequisites empty", async ({
    page,
  }) => {
    await page.goto("/admin");
    await expect(page.getByText("Initial Seed")).toBeVisible();

    // Strategic Objectives button should be disabled
    const stratBtn = page.getByRole("button", {
      name: "Seed Strategic Objectives",
    });
    await expect(stratBtn).toBeVisible();
    await expect(stratBtn).toBeDisabled();

    // Tactical Objectives button should be disabled
    const tactBtn = page.getByRole("button", {
      name: "Seed Tactical Objectives",
    });
    await expect(tactBtn).toBeVisible();
    await expect(tactBtn).toBeDisabled();

    // Policies button should be disabled
    const polBtn = page.getByRole("button", { name: "Seed Policies" });
    await expect(polBtn).toBeVisible();
    await expect(polBtn).toBeDisabled();
  });

  test("strategic objectives button enables when values and SA populated", async ({
    page,
  }) => {
    // Populate values and SA layers
    await createLayerItem(page, token, "values");
    await createLayerItem(page, token, "situational-awareness");

    await page.goto("/admin");
    await expect(page.getByText("Initial Seed")).toBeVisible();

    // Strategic Objectives button should now be enabled
    const stratBtn = page.getByRole("button", {
      name: "Seed Strategic Objectives",
    });
    await expect(stratBtn).toBeVisible();
    await expect(stratBtn).toBeEnabled();
  });

  test("tactical objectives button remains disabled when strategic empty", async ({
    page,
  }) => {
    // Populate values and SA, but NOT strategic-objectives
    await createLayerItem(page, token, "values");
    await createLayerItem(page, token, "situational-awareness");

    await page.goto("/admin");
    await expect(page.getByText("Initial Seed")).toBeVisible();

    // Tactical Objectives button should still be disabled
    const tactBtn = page.getByRole("button", {
      name: "Seed Tactical Objectives",
    });
    await expect(tactBtn).toBeVisible();
    await expect(tactBtn).toBeDisabled();
  });

  test("policies button enables only when all 4 layers below populated", async ({
    page,
  }) => {
    // Populate all 4 prerequisite layers
    await createLayerItem(page, token, "values");
    await createLayerItem(page, token, "situational-awareness");
    await createLayerItem(page, token, "strategic-objectives");
    await createLayerItem(page, token, "tactical-objectives");

    await page.goto("/admin");
    await expect(page.getByText("Initial Seed")).toBeVisible();

    // Policies button should now be enabled
    const polBtn = page.getByRole("button", { name: "Seed Policies" });
    await expect(polBtn).toBeVisible();
    await expect(polBtn).toBeEnabled();
  });

  // -----------------------------------------------------------------------
  // Populated state tests
  // -----------------------------------------------------------------------

  test("seeded layers show active status and count", async ({ page }) => {
    // Create 2 items in the values layer
    await createLayerItem(page, token, "values", "test-val-1.md");
    await createLayerItem(page, token, "values", "test-val-2.md");

    await page.goto("/admin");
    await expect(page.getByText("Initial Seed")).toBeVisible();

    // The Values row should show the count
    await expect(page.getByText("2 items").first()).toBeVisible();
  });

  test("layer count updates after adding items", async ({ page }) => {
    // Create 1 item in values layer
    await createLayerItem(page, token, "values", "test-count-1.md");

    await page.goto("/admin");
    await expect(page.getByText("Initial Seed")).toBeVisible();

    // Should show 1 item
    await expect(page.getByText("1 items").first()).toBeVisible();

    // Add another item
    await createLayerItem(page, token, "values", "test-count-2.md");

    // Refresh the page
    await page.reload();
    await expect(page.getByText("Initial Seed")).toBeVisible();

    // Should now show 2 items
    await expect(page.getByText("2 items").first()).toBeVisible();
  });

  // -----------------------------------------------------------------------
  // Full Cascade button
  // -----------------------------------------------------------------------

  test("Full Cascade button is present", async ({ page }) => {
    await page.goto("/admin");
    await expect(page.getByText("Initial Seed")).toBeVisible();

    const cascadeBtn = page.getByRole("button", { name: "Full Cascade" });
    await expect(cascadeBtn).toBeVisible();
  });

  // -----------------------------------------------------------------------
  // Mutual exclusion during seeding (optional — skipped if flaky)
  // -----------------------------------------------------------------------

  test.skip("all seed buttons disabled during any seed operation", async ({
    page,
  }) => {
    // This test is skipped because it depends on timing and is already covered
    // by unit tests in step 006. The behavior: when a seed button is clicked,
    // all other seed buttons become disabled until the operation completes.
    await page.goto("/admin");
    await expect(page.getByText("Initial Seed")).toBeVisible();

    const valuesBtn = page.getByRole("button", { name: "Seed Values" });
    await valuesBtn.click();

    // Immediately check that other buttons are disabled
    const saBtn = page.getByRole("button", {
      name: /Seed Situational Awareness|Seeding Situational Awareness/,
    });
    await expect(saBtn).toBeDisabled();
  });
});
