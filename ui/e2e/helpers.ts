/**
 * Shared E2E test helpers.
 *
 * Provides a resilient `setupAndLogin` that works regardless of whether
 * the database already contains users. All tests share a single admin
 * account so they don't conflict with each other.
 */

import { expect, Page } from "@playwright/test";

/** Shared test admin credentials (used by every E2E test file). */
export const TEST_ADMIN_EMAIL = "admin@test.com";
export const TEST_ADMIN_PASSWORD = "password123";

/**
 * Register the first admin user (if no users exist) and log in.
 *
 * This function is idempotent:
 * - On a fresh database it registers the first user (who becomes admin).
 * - If users already exist the registration 403s silently and we just log in.
 */
export async function setupAndLogin(page: Page): Promise<void> {
  // Attempt registration — silently ignore 403 (registration closed).
  await page.request.post("/api/auth/register", {
    data: { email: TEST_ADMIN_EMAIL, password: TEST_ADMIN_PASSWORD },
  });

  await page.goto("/login");
  await page.getByLabel(/email/i).fill(TEST_ADMIN_EMAIL);
  await page.getByLabel("Password", { exact: true }).fill(TEST_ADMIN_PASSWORD);
  await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();
  await expect(page).toHaveURL(/\/$/);
}

/**
 * Get a JWT token for the shared test admin account.
 *
 * Useful when tests need to make authenticated API calls.
 */
export async function getAdminToken(page: Page): Promise<string> {
  const loginResp = await page.request.post("/api/auth/login", {
    data: { email: TEST_ADMIN_EMAIL, password: TEST_ADMIN_PASSWORD },
  });
  const { token } = await loginResp.json();
  return token;
}
