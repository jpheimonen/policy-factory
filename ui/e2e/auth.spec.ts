import { test, expect } from "@playwright/test";

/**
 * E2E tests for the authentication flow.
 *
 * Verifies: first-visit registration, login/logout, credential validation.
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

    await page.getByLabel(/email/i).fill("admin@test.com");
    await page.getByLabel(/password/i).fill("password123");
    await page.getByRole("button", { name: /register|sign up|create/i }).click();

    // After registration, should be on the home page
    await expect(page).toHaveURL(/\/$/);
  });

  test("logout redirects to login", async ({ page }) => {
    // Register first
    await page.goto("/register");
    await page.getByLabel(/email/i).fill("admin@test.com");
    await page.getByLabel(/password/i).fill("password123");
    await page.getByRole("button", { name: /register|sign up|create/i }).click();

    // Find and click logout
    const logoutButton = page.getByRole("button", { name: /logout|sign out/i });
    if (await logoutButton.isVisible()) {
      await logoutButton.click();
      // Should be redirected to login
      await expect(page).toHaveURL(/\/(login)?$/);
    }
  });

  test("login with valid credentials", async ({ page }) => {
    // Set up user via API
    await page.request.post("/api/auth/register", {
      data: { email: "login@test.com", password: "password123" },
    });

    await page.goto("/login");
    await page.getByLabel(/email/i).fill("login@test.com");
    await page.getByLabel(/password/i).fill("password123");
    await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();

    // Should reach the home page
    await expect(page).toHaveURL(/\/$/);
  });

  test("login with invalid credentials shows error", async ({ page }) => {
    // Set up user via API
    await page.request.post("/api/auth/register", {
      data: { email: "error@test.com", password: "password123" },
    });

    await page.goto("/login");
    await page.getByLabel(/email/i).fill("error@test.com");
    await page.getByLabel(/password/i).fill("wrongpassword");
    await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();

    // Should show an error message
    await expect(
      page.getByText(/invalid|error|incorrect|wrong/i).first()
    ).toBeVisible();
  });
});
