/**
 * Shared E2E test helpers.
 *
 * Provides a resilient `setupAndLogin` that works regardless of whether
 * the database already contains users. All tests share a single admin
 * account so they don't conflict with each other.
 */

import { expect, Page } from "@playwright/test";

/**
 * Shared test admin credentials (used by every E2E test file).
 *
 * Reads from POLICY_FACTORY_ADMIN_EMAIL / POLICY_FACTORY_ADMIN_PASSWORD
 * so E2E tests use the same credentials as the running server.
 * Falls back to admin@admin.com / admin (matching the server defaults).
 */
export const TEST_ADMIN_EMAIL =
  process.env.POLICY_FACTORY_ADMIN_EMAIL || "admin@admin.com";
export const TEST_ADMIN_PASSWORD =
  process.env.POLICY_FACTORY_ADMIN_PASSWORD || "admin";

/**
 * Register the first admin user (if no users exist) and log in.
 *
 * This function is idempotent:
 * - On a fresh database it registers the first user (who becomes admin).
 * - If users already exist the registration 403s silently and we just log in.
 * - If already logged in (from browser cache), skips login flow.
 */
export async function setupAndLogin(page: Page): Promise<void> {
  // Attempt registration — silently ignore 403 (registration closed).
  await page.request.post("/api/auth/register", {
    data: { email: TEST_ADMIN_EMAIL, password: TEST_ADMIN_PASSWORD },
  });

  // Navigate to home page first to check login state
  await page.goto("/");

  // Wait for page to stabilize (either login redirect or home page load)
  await page.waitForLoadState("networkidle");

  // Check if we're on the login page or already logged in
  const currentUrl = page.url();
  if (currentUrl.includes("/login")) {
    // Not logged in — perform login
    await page.getByLabel(/email/i).fill(TEST_ADMIN_EMAIL);
    await page.getByLabel("Password", { exact: true }).fill(TEST_ADMIN_PASSWORD);
    await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();
    await expect(page).toHaveURL(/\/$/);
  } else if (currentUrl.endsWith("/") || currentUrl.includes("/layers")) {
    // Already logged in — verify by checking for user indicator or nav
    const logoutButton = page.getByRole("button", { name: /log\s*out/i });
    const isLoggedIn = await logoutButton.isVisible({ timeout: 2000 }).catch(() => false);
    if (!isLoggedIn) {
      // Session might be stale, go to login
      await page.goto("/login");
      await page.waitForLoadState("networkidle");
      await page.getByLabel(/email/i).fill(TEST_ADMIN_EMAIL);
      await page.getByLabel("Password", { exact: true }).fill(TEST_ADMIN_PASSWORD);
      await page.getByRole("button", { name: /log\s*in|sign\s*in/i }).click();
      await expect(page).toHaveURL(/\/$/);
    }
    // else: Already logged in, nothing to do
  }
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

// ── Conversation Test Helpers ────────────────────────────────────────

/**
 * Create a test conversation via API.
 *
 * @param page - Playwright page for API requests
 * @param token - Auth token (from getAdminToken)
 * @param layerSlug - Layer slug (e.g., "values", "philosophy")
 * @param filename - Optional filename for item-level conversation
 * @returns Conversation ID
 */
export async function createTestConversation(
  page: Page,
  token: string,
  layerSlug: string,
  filename?: string,
): Promise<string | null> {
  const body: { layer_slug: string; filename?: string } = {
    layer_slug: layerSlug,
  };
  if (filename) {
    body.filename = filename;
  }

  const resp = await page.request.post("/api/conversations/", {
    headers: { Authorization: `Bearer ${token}` },
    data: body,
  });

  if (!resp.ok()) {
    // Conversation API might not be available — return null for graceful degradation
    console.warn(`Failed to create conversation: ${resp.status()}`);
    return null;
  }

  const data = await resp.json();
  return data.id;
}

/**
 * Send a test message to a conversation via API.
 *
 * @param page - Playwright page for API requests
 * @param token - Auth token
 * @param conversationId - Conversation ID
 * @param content - Message content
 * @returns Message ID
 */
export async function sendTestMessage(
  page: Page,
  token: string,
  conversationId: string,
  content: string,
): Promise<string> {
  const resp = await page.request.post(
    `/api/conversations/${conversationId}/messages`,
    {
      headers: { Authorization: `Bearer ${token}` },
      data: { content },
    },
  );

  if (!resp.ok()) {
    throw new Error(`Failed to send message: ${resp.status()}`);
  }

  const data = await resp.json();
  return data.message_id;
}

/**
 * Wait for streaming to complete.
 *
 * Waits for the streaming indicator (typing dots) to disappear,
 * indicating the AI response has finished.
 *
 * @param page - Playwright page
 * @param timeout - Maximum wait time in ms (default: 30s)
 */
export async function waitForStreamingComplete(
  page: Page,
  timeout: number = 30000,
): Promise<void> {
  // Wait for the streaming indicator to appear first (if it hasn't yet)
  const streamingIndicator = page.locator(
    "[class*='TypingIndicator'], [class*='StreamingCursor']",
  );

  // Then wait for it to disappear (streaming complete)
  try {
    await streamingIndicator.waitFor({ state: "hidden", timeout });
  } catch {
    // If it never appeared, streaming might have completed very fast
    // or there was an error — either way, continue
  }
}

/**
 * Create a test item via API.
 *
 * @param page - Playwright page for API requests
 * @param token - Auth token
 * @param layerSlug - Layer slug
 * @param filename - Filename for the item
 * @param title - Item title
 * @param body - Item body content
 */
export async function createTestItem(
  page: Page,
  token: string,
  layerSlug: string,
  filename: string,
  title: string,
  body: string = "",
): Promise<void> {
  const resp = await page.request.post(`/api/layers/${layerSlug}/items`, {
    headers: { Authorization: `Bearer ${token}` },
    data: {
      filename,
      frontmatter: {
        title,
        status: "active",
        references: [],
      },
      body,
    },
  });

  if (!resp.ok()) {
    // Item might already exist — that's okay
    const status = resp.status();
    if (status !== 409 && status !== 400) {
      throw new Error(`Failed to create item: ${status}`);
    }
  }
}
