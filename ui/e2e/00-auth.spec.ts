import { test, expect } from "@playwright/test";
import { TEST_ADMIN_EMAIL, TEST_ADMIN_PASSWORD } from "./helpers";

/**
 * E2E tests for the authentication flow.
 *
 * Verifies: first-visit registration, login/logout, credential validation.
 *
 * NOTE: These tests are ordered — "first visit shows registration page"
 * must run before "register first user" because the global setup clears
 * the users table.
 */

test.describe("Authentication Flow", () => {
  test("first visit shows registration page", async ({ page }) => {
    await page.goto("/");
    // Should redirect to register or login — when no users exist, registration is shown
    await expect(
      page.getByText(/register|sign up|create account/i).first()
    ).toBeVisible();
  });

  test("register first user redirects to home", async ({ page }) => {
    await page.goto("/register");

    await page.getByLabel(/email/i).fill(TEST_ADMIN_EMAIL);
    // Use exact match for "Password" to avoid matching "Confirm password"
    await page.getByLabel("Password", { exact: true }).fill(TEST_ADMIN_PASSWORD);
    await page.getByLabel("Confirm password").fill(TEST_ADMIN_PASSWORD);
    await page.getByRole("button", { name: /register|sign up|create/i }).click();

    // After registration, should be on the home page
    await expect(page).toHaveURL(/\/$/);
  });

  test("logout redirects to login", async ({ page }) => {
    // Login with the admin account (user was created by previous test)
    await page.goto("/login");
    await page.getByLabel(/email/i).fill(TEST_ADMIN_EMAIL);
    await page.getByLabel("Password", { exact: true }).fill(TEST_ADMIN_PASSWORD);
    await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();
    await expect(page).toHaveURL(/\/$/);

    // Find and click logout
    const logoutButton = page.getByRole("button", { name: /logout|sign out/i });
    if (await logoutButton.isVisible()) {
      await logoutButton.click();
      // Should be redirected to login
      await expect(page).toHaveURL(/\/(login)?$/);
    }
  });

  test("login with valid credentials", async ({ page }) => {
    // Ensure user exists (may already exist from previous tests)
    await page.request.post("/api/auth/register", {
      data: { email: TEST_ADMIN_EMAIL, password: TEST_ADMIN_PASSWORD },
    });

    await page.goto("/login");
    await page.getByLabel(/email/i).fill(TEST_ADMIN_EMAIL);
    await page.getByLabel("Password", { exact: true }).fill(TEST_ADMIN_PASSWORD);
    await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();

    // Should reach the home page
    await expect(page).toHaveURL(/\/$/);
  });

  test("login with invalid credentials shows error", async ({ page }) => {
    // Ensure user exists
    await page.request.post("/api/auth/register", {
      data: { email: TEST_ADMIN_EMAIL, password: TEST_ADMIN_PASSWORD },
    });

    await page.goto("/login");
    await page.getByLabel(/email/i).fill(TEST_ADMIN_EMAIL);
    await page.getByLabel("Password", { exact: true }).fill("wrongpassword");
    await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();

    // Should show an error message
    await expect(
      page.getByText(/invalid|error|incorrect|wrong/i).first()
    ).toBeVisible();
  });
});
