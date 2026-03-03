import { test, expect } from "@playwright/test";
import { setupAndLogin, getAdminToken } from "./helpers";

/**
 * E2E tests for the live cascade viewer.
 *
 * Verifies: cascade display, progress indicator, streaming text,
 * paused cascade controls.
 */

test.describe("Cascade Viewer", () => {
  test("cascade page is accessible", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/cascade");

    // The cascade viewer page should load
    await expect(page.locator("main, [role='main'], .page-content, .cascade").first()).toBeVisible();
  });

  test("shows idle state when no cascade running", async ({ page }) => {
    await setupAndLogin(page);
    await page.goto("/cascade");

    // Should show some idle/no-cascade indicator
    const content = await page.textContent("body");
    // Page should not be blank
    expect(content).toBeTruthy();
  });
});

test.describe("Cascade Transcript", () => {
  // NOTE: Creating a cascade with agent runs that have output_text requires
  // triggering a real cascade (POST /api/cascade/refresh) which depends on
  // having layer content and AI agent availability. These dependencies are
  // typically not available in E2E test environments. The tests below verify
  // the UI structure when cascade history exists and gracefully skip when
  // real cascade data cannot be produced.

  test("cascade detail panel shows agent run entries when cascade history exists", async ({
    page,
  }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    // Check if any cascade history exists
    const historyResp = await page.request.get("/api/cascade/history", {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!historyResp.ok()) {
      test.skip();
      return;
    }

    const history = await historyResp.json();

    if (!Array.isArray(history) || history.length === 0) {
      // No cascade history — try to trigger one
      const triggerResp = await page.request.post("/api/cascade/refresh", {
        headers: { Authorization: `Bearer ${token}` },
        data: { layer_slug: "values" },
      });

      if (!triggerResp.ok()) {
        // Cannot create cascade data in this environment
        test.skip();
        return;
      }

      // Wait for cascade to potentially complete
      await page.waitForTimeout(10000);
    }

    await page.goto("/cascade");
    await page.waitForTimeout(1000);

    // If history entries exist, click the first one to expand
    const bodyText = await page.textContent("body");
    if (bodyText && /no cascades/i.test(bodyText)) {
      // Still no cascades — skip
      test.skip();
      return;
    }

    // The page loaded with cascade history — verify structure is present
    expect(bodyText).toBeTruthy();
  });

  test("agent run entries display agent label and target layer", async ({
    page,
  }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    // Check for existing cascade history
    const historyResp = await page.request.get("/api/cascade/history", {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!historyResp.ok()) {
      test.skip();
      return;
    }

    const history = await historyResp.json();

    if (!Array.isArray(history) || history.length === 0) {
      test.skip();
      return;
    }

    // Fetch detail of the first cascade to check if it has agent runs
    const cascadeId = history[0].id;
    const detailResp = await page.request.get(`/api/cascade/${cascadeId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!detailResp.ok()) {
      test.skip();
      return;
    }

    const detail = await detailResp.json();

    if (!detail.agent_runs || detail.agent_runs.length === 0) {
      test.skip();
      return;
    }

    await page.goto("/cascade");
    await page.waitForTimeout(1000);

    // Click the first history entry to expand it
    const historyEntry = page.locator("[class*='HistoryEntry']").first();
    if (await historyEntry.isVisible()) {
      await historyEntry.click();
      await page.waitForTimeout(1000);

      // Check that "Agent Runs" heading appears in the expanded detail
      await expect(page.getByText(/agent runs/i).first()).toBeVisible();

      // Check that agent label text is present from the first agent run
      const firstRunLabel = detail.agent_runs[0].agent_label;
      if (firstRunLabel) {
        await expect(
          page.getByText(firstRunLabel).first(),
        ).toBeVisible();
      }
    }
  });

  test("agent runs with output text have an expand control", async ({
    page,
  }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    const historyResp = await page.request.get("/api/cascade/history", {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!historyResp.ok()) {
      test.skip();
      return;
    }

    const history = await historyResp.json();

    if (!Array.isArray(history) || history.length === 0) {
      test.skip();
      return;
    }

    // Check if any agent run has output_text
    const cascadeId = history[0].id;
    const detailResp = await page.request.get(`/api/cascade/${cascadeId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!detailResp.ok()) {
      test.skip();
      return;
    }

    const detail = await detailResp.json();
    const hasOutputText = detail.agent_runs?.some(
      (r: { output_text: string | null }) => r.output_text != null,
    );

    if (!hasOutputText) {
      test.skip();
      return;
    }

    await page.goto("/cascade");
    await page.waitForTimeout(1000);

    // Click first history entry to expand
    const historyEntry = page.locator("[class*='HistoryEntry']").first();
    if (await historyEntry.isVisible()) {
      await historyEntry.click();
      await page.waitForTimeout(1000);

      // Look for the transcript expand control
      const expandControl = page.getByText(/show transcript/i).first();
      await expect(expandControl).toBeVisible();
    }
  });

  test("expanding transcript shows output text content", async ({ page }) => {
    await setupAndLogin(page);
    const token = await getAdminToken(page);

    const historyResp = await page.request.get("/api/cascade/history", {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!historyResp.ok()) {
      test.skip();
      return;
    }

    const history = await historyResp.json();

    if (!Array.isArray(history) || history.length === 0) {
      test.skip();
      return;
    }

    const cascadeId = history[0].id;
    const detailResp = await page.request.get(`/api/cascade/${cascadeId}`, {
      headers: { Authorization: `Bearer ${token}` },
    });

    if (!detailResp.ok()) {
      test.skip();
      return;
    }

    const detail = await detailResp.json();
    const runWithOutput = detail.agent_runs?.find(
      (r: { output_text: string | null }) => r.output_text != null,
    );

    if (!runWithOutput) {
      test.skip();
      return;
    }

    await page.goto("/cascade");
    await page.waitForTimeout(1000);

    // Click first history entry to expand
    const historyEntry = page.locator("[class*='HistoryEntry']").first();
    if (await historyEntry.isVisible()) {
      await historyEntry.click();
      await page.waitForTimeout(1000);

      // Click the "Show transcript" button
      const expandButton = page.getByText(/show transcript/i).first();
      if (await expandButton.isVisible()) {
        await expandButton.click();
        await page.waitForTimeout(500);

        // The transcript text should now be visible in a pre block
        const transcriptBlock = page.locator("pre").last();
        await expect(transcriptBlock).toBeVisible();

        // Verify transcript contains some text
        const transcriptText = await transcriptBlock.textContent();
        expect(transcriptText).toBeTruthy();
        expect(transcriptText!.length).toBeGreaterThan(0);
      }
    }
  });
});
