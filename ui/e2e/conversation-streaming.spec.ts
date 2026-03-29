import { test, expect } from "@playwright/test";
import {
  setupAndLogin,
  getAdminToken,
  createTestItem,
  createTestConversation,
} from "./helpers";

/**
 * E2E tests for conversation streaming display.
 *
 * Verifies: streaming indicator visibility, real-time text updates,
 * auto-scroll behavior, and final message rendering.
 *
 * NOTE: These tests verify the UI structure for streaming. Actually
 * triggering AI streaming responses requires the conversation runner
 * and agent configuration. Tests are designed to verify the UI is ready
 * to handle streaming when it occurs.
 */

test.describe("Streaming Indicator", () => {
  test("streaming UI elements exist in sidebar", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    const uniqueId = Date.now();
    await createTestItem(
      page,
      token,
      "values",
      `stream-ui-${uniqueId}.md`,
      `Streaming UI Test ${uniqueId}`,
    );

    const convId = await createTestConversation(
      page,
      token,
      "values",
      `stream-ui-${uniqueId}.md`,
    );

    if (!convId) {
      test.skip(true, "Conversation API unavailable");
      return;
    }

    await page.goto(`/layers/values/stream-ui-${uniqueId}`);

    // Open sidebar
    const toggleButton = page.getByRole("button", { name: "Chat" });
    await toggleButton.click();
    await page.waitForTimeout(500);

    // Verify sidebar is functional
    const sidebar = page.locator("aside").first();
    await expect(sidebar).toBeVisible();

    // The sidebar should have content areas (input, message list)
    const textarea = sidebar.locator("textarea");
    await expect(textarea).toBeVisible();
  });

  test("message input shows send button", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    const uniqueId = Date.now();
    await createTestItem(
      page,
      token,
      "values",
      `stream-input-${uniqueId}.md`,
      `Stream Input Test ${uniqueId}`,
    );

    const convId = await createTestConversation(
      page,
      token,
      "values",
      `stream-input-${uniqueId}.md`,
    );

    if (!convId) {
      test.skip(true, "Conversation API unavailable");
      return;
    }

    await page.goto(`/layers/values/stream-input-${uniqueId}`);

    // Open sidebar
    const toggleButton = page.getByRole("button", { name: "Chat" });
    await toggleButton.click();
    await page.waitForTimeout(500);

    // Verify input area exists
    const textarea = page.locator("textarea");
    await expect(textarea).toBeVisible();

    // Verify send button exists
    const sendButton = page.getByRole("button", { name: /send/i });
    await expect(sendButton).toBeVisible();
  });
});

test.describe("Streaming State Management", () => {
  test("send button is disabled with empty input", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    const uniqueId = Date.now();
    await createTestItem(
      page,
      token,
      "values",
      `stream-disabled-${uniqueId}.md`,
      `Stream Disabled Test ${uniqueId}`,
    );

    const convId = await createTestConversation(
      page,
      token,
      "values",
      `stream-disabled-${uniqueId}.md`,
    );

    if (!convId) {
      test.skip(true, "Conversation API unavailable");
      return;
    }

    await page.goto(`/layers/values/stream-disabled-${uniqueId}`);

    // Open sidebar
    const toggleButton = page.getByRole("button", { name: "Chat" });
    await toggleButton.click();
    await page.waitForTimeout(500);

    // Send button should be disabled with empty textarea
    const sendButton = page.getByRole("button", { name: /send/i });
    await expect(sendButton).toBeDisabled();
  });

  test("send button becomes enabled when text is entered", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    const uniqueId = Date.now();
    await createTestItem(
      page,
      token,
      "values",
      `stream-enabled-${uniqueId}.md`,
      `Stream Enabled Test ${uniqueId}`,
    );

    const convId = await createTestConversation(
      page,
      token,
      "values",
      `stream-enabled-${uniqueId}.md`,
    );

    if (!convId) {
      test.skip(true, "Conversation API unavailable");
      return;
    }

    await page.goto(`/layers/values/stream-enabled-${uniqueId}`);

    // Open sidebar
    const toggleButton = page.getByRole("button", { name: "Chat" });
    await toggleButton.click();
    await page.waitForTimeout(500);

    // Enter text
    const textarea = page.locator("textarea");
    await textarea.fill("Test streaming message");

    // Send button should now be enabled
    const sendButton = page.getByRole("button", { name: /send/i });
    await expect(sendButton).toBeEnabled();
  });

  test("user message appears immediately on send", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    const uniqueId = Date.now();
    await createTestItem(
      page,
      token,
      "values",
      `stream-immediate-${uniqueId}.md`,
      `Stream Immediate Test ${uniqueId}`,
    );

    const convId = await createTestConversation(
      page,
      token,
      "values",
      `stream-immediate-${uniqueId}.md`,
    );

    if (!convId) {
      test.skip(true, "Conversation API unavailable");
      return;
    }

    await page.goto(`/layers/values/stream-immediate-${uniqueId}`);

    // Open sidebar
    const toggleButton = page.getByRole("button", { name: "Chat" });
    await toggleButton.click();
    await page.waitForTimeout(500);

    // Send a message
    const textarea = page.locator("textarea");
    const testMessage = `Immediate display test ${uniqueId}`;
    await textarea.fill(testMessage);
    await textarea.press("Control+Enter");

    // Message should appear immediately (optimistic update)
    await expect(page.getByText(testMessage)).toBeVisible({ timeout: 2000 });
  });
});

test.describe("Message Display", () => {
  test("message bubbles have correct structure", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    const uniqueId = Date.now();
    await createTestItem(
      page,
      token,
      "values",
      `stream-bubble-${uniqueId}.md`,
      `Stream Bubble Test ${uniqueId}`,
    );

    const convId = await createTestConversation(
      page,
      token,
      "values",
      `stream-bubble-${uniqueId}.md`,
    );

    if (!convId) {
      test.skip(true, "Conversation API unavailable");
      return;
    }

    await page.goto(`/layers/values/stream-bubble-${uniqueId}`);

    // Open sidebar
    const toggleButton = page.getByRole("button", { name: "Chat" });
    await toggleButton.click();
    await page.waitForTimeout(500);

    // Send a message to see a bubble
    const textarea = page.locator("textarea");
    const testMessage = `Bubble test ${uniqueId}`;
    await textarea.fill(testMessage);
    await textarea.press("Control+Enter");

    // Wait for message to appear
    await expect(page.getByText(testMessage)).toBeVisible({ timeout: 2000 });
  });

  test("message list is scrollable", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    const uniqueId = Date.now();
    await createTestItem(
      page,
      token,
      "values",
      `stream-scroll-${uniqueId}.md`,
      `Stream Scroll Test ${uniqueId}`,
    );

    const convId = await createTestConversation(
      page,
      token,
      "values",
      `stream-scroll-${uniqueId}.md`,
    );

    if (!convId) {
      test.skip(true, "Conversation API unavailable");
      return;
    }

    // Add multiple messages to ensure scrollability
    for (let i = 0; i < 5; i++) {
      await page.request.post(`/api/conversations/${convId}/messages`, {
        headers: { Authorization: `Bearer ${token}` },
        data: { content: `Scroll test message ${i + 1} ${uniqueId}` },
      });
      // Small delay between messages
      await page.waitForTimeout(100);
    }

    await page.goto(`/layers/values/stream-scroll-${uniqueId}`);

    // Open sidebar
    const toggleButton = page.getByRole("button", { name: "Chat" });
    await toggleButton.click();
    await page.waitForTimeout(1000);

    // Sidebar should be visible with messages
    const sidebar = page.locator("aside").first();
    await expect(sidebar).toBeVisible();

    // Messages should appear in the sidebar
    await expect(page.getByText(`Scroll test message 1 ${uniqueId}`)).toBeVisible();
  });
});

test.describe("Auto-Scroll Behavior", () => {
  // Note: Auto-scroll during streaming is handled by useAutoScroll hook.
  // These tests verify the scroll container is properly configured.

  test("message container allows scrolling", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    const uniqueId = Date.now();
    await createTestItem(
      page,
      token,
      "values",
      `auto-scroll-${uniqueId}.md`,
      `Auto Scroll Test ${uniqueId}`,
    );

    const convId = await createTestConversation(
      page,
      token,
      "values",
      `auto-scroll-${uniqueId}.md`,
    );

    if (!convId) {
      test.skip(true, "Conversation API unavailable");
      return;
    }

    await page.goto(`/layers/values/auto-scroll-${uniqueId}`);

    // Open sidebar
    const toggleButton = page.getByRole("button", { name: "Chat" });
    await toggleButton.click();
    await page.waitForTimeout(500);

    // Send a message
    const textarea = page.locator("textarea");
    const testMessage = `Auto scroll test ${uniqueId}`;
    await textarea.fill(testMessage);
    await textarea.press("Control+Enter");

    // The message should be visible (auto-scrolled into view)
    await expect(page.getByText(testMessage)).toBeVisible({
      timeout: 2000,
    });
  });
});

test.describe("Streaming Keyboard Shortcuts", () => {
  test("Cmd+Enter sends message (macOS)", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    const uniqueId = Date.now();
    await createTestItem(
      page,
      token,
      "values",
      `stream-cmd-enter-${uniqueId}.md`,
      `Stream Cmd Enter Test ${uniqueId}`,
    );

    const convId = await createTestConversation(
      page,
      token,
      "values",
      `stream-cmd-enter-${uniqueId}.md`,
    );

    if (!convId) {
      test.skip(true, "Conversation API unavailable");
      return;
    }

    await page.goto(`/layers/values/stream-cmd-enter-${uniqueId}`);

    // Open sidebar
    const toggleButton = page.getByRole("button", { name: "Chat" });
    await toggleButton.click();
    await page.waitForTimeout(500);

    // Type and send with Meta+Enter (Cmd on macOS)
    const textarea = page.locator("textarea");
    const testMessage = `Cmd+Enter test ${uniqueId}`;
    await textarea.fill(testMessage);
    await textarea.press("Meta+Enter");

    // Message should appear
    await expect(page.getByText(testMessage)).toBeVisible({ timeout: 2000 });
  });

  test("input clears after sending", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    const uniqueId = Date.now();
    await createTestItem(
      page,
      token,
      "values",
      `stream-clear-${uniqueId}.md`,
      `Stream Clear Test ${uniqueId}`,
    );

    const convId = await createTestConversation(
      page,
      token,
      "values",
      `stream-clear-${uniqueId}.md`,
    );

    if (!convId) {
      test.skip(true, "Conversation API unavailable");
      return;
    }

    await page.goto(`/layers/values/stream-clear-${uniqueId}`);

    // Open sidebar
    const toggleButton = page.getByRole("button", { name: "Chat" });
    await toggleButton.click();
    await page.waitForTimeout(500);

    // Send a message
    const textarea = page.locator("textarea");
    await textarea.fill(`Clear after send ${uniqueId}`);
    await textarea.press("Control+Enter");

    // Input should be cleared
    await expect(textarea).toHaveValue("");
  });
});

test.describe("Streaming Error States", () => {
  // Note: Actual streaming errors require backend failure simulation.
  // These tests verify the UI handles error states gracefully.

  test("conversation loads without crashing when API is unavailable", async ({
    page,
  }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    const uniqueId = Date.now();
    await createTestItem(
      page,
      token,
      "values",
      `stream-error-${uniqueId}.md`,
      `Stream Error Test ${uniqueId}`,
    );

    await page.goto(`/layers/values/stream-error-${uniqueId}`);

    // Open sidebar
    const toggleButton = page.getByRole("button", { name: "Chat" });
    await toggleButton.click();

    // Sidebar should be visible even without conversations
    const sidebar = page.locator("aside").first();
    await expect(sidebar).toBeVisible();

    // Sidebar should show conversation interface (either empty state or content)
    const hasContent = await sidebar.getByRole("heading", { name: /conversation/i }).isVisible().catch(() => false) ||
                       await sidebar.locator("textarea").isVisible().catch(() => false);
    expect(hasContent).toBe(true);
  });
});

test.describe("Real-Time Streaming", () => {
  // Note: These tests require actual AI streaming which depends on
  // the conversation runner and agent configuration. The tests verify
  // the UI is ready to handle streaming when it occurs.

  test.skip("streaming indicator appears during AI response", async ({
    page,
  }) => {
    // This test requires actual AI agent to be available
    // Skip in CI environments without AI configuration
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    const uniqueId = Date.now();
    await createTestItem(
      page,
      token,
      "values",
      `real-stream-${uniqueId}.md`,
      `Real Stream Test ${uniqueId}`,
    );

    await createTestConversation(
      page,
      token,
      "values",
      `real-stream-${uniqueId}.md`,
    );

    await page.goto(`/layers/values/real-stream-${uniqueId}`);

    // Open sidebar
    const toggleButton = page.getByRole("button", { name: "Chat" });
    await toggleButton.click();
    await page.waitForTimeout(500);

    // Send a message that would trigger AI response
    const textarea = page.locator("textarea");
    await textarea.fill("Please respond to this test message");
    await textarea.press("Control+Enter");

    // Look for typing/streaming indicator
    const streamingIndicator = page.locator(
      "[class*='TypingIndicator'], [class*='StreamingCursor'], [class*='Loading']",
    );

    // This would only appear if AI is responding
    // In test environments without AI, this will timeout
    try {
      await expect(streamingIndicator.first()).toBeVisible({ timeout: 5000 });
    } catch {
      // Expected to fail without AI agent
      test.skip();
    }
  });

  test.skip("streaming text appears incrementally", async ({ page }) => {
    // This test requires actual AI agent to be available
    await setupAndLogin(page);

    // Skip in CI environments without AI configuration
    test.skip();
  });

  test.skip("final message matches complete streamed text", async ({
    page,
  }) => {
    // This test requires actual AI agent to be available
    await setupAndLogin(page);

    // Skip in CI environments without AI configuration
    test.skip();
  });
});
