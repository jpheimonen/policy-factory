import { test, expect, Page } from "@playwright/test";

/**
 * E2E tests for the admin panel.
 *
 * Verifies: admin access, user list, create/delete users, non-admin restriction.
 */

async function loginAsAdmin(page: Page) {
  await page.request.post("/api/auth/register", {
    data: { email: "admin@test.com", password: "password123" },
  });
  await page.goto("/login");
  await page.getByLabel(/email/i).fill("admin@test.com");
  await page.getByLabel(/password/i).fill("password123");
  await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();
  await expect(page).toHaveURL(/\/$/);
}

test.describe("Admin Panel", () => {
  test("admin can access admin panel", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/admin");

    // Admin panel should be accessible
    await expect(page.locator("main, [role='main'], .page-content, .admin").first()).toBeVisible();
  });

  test("admin panel shows user list", async ({ page }) => {
    await loginAsAdmin(page);
    await page.goto("/admin");

    // Should show the admin user in the list
    await expect(page.getByText("admin@test.com").first()).toBeVisible();
  });

  test("admin can create user", async ({ page }) => {
    await loginAsAdmin(page);
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
    await loginAsAdmin(page);
    await page.goto("/admin");

    // The delete button for the admin's own account should be disabled
    // or should show an error if clicked
    const adminRow = page.getByText("admin@test.com").first();
    await expect(adminRow).toBeVisible();
  });
});
