import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for Policy Factory E2E tests.
 *
 * - Sequential execution (single worker) to avoid database state conflicts
 * - 30-second timeout per test
 * - Traces captured on first retry
 * - Screenshots captured on failure
 * - Base URL pointing to the frontend dev server (localhost:5173)
 * - Chromium only (single browser project)
 * - CI-aware: retries enabled in CI, disabled locally
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? "github" : "list",

  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
