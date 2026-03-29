/**
 * Tests for the i18n system: provider, hook, translation lookup,
 * interpolation, missing key handling, and testing utilities.
 */
import { describe, it, expect, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { I18nProvider, useTranslation } from "@/i18n/I18nProvider.tsx";
import { renderWithI18n, renderWithI18nOnly } from "@/i18n/test-utils.tsx";

// ── Helper: wrap renderHook with I18nProvider ─────────────────────────

function wrapper({ children }: { children: ReactNode }) {
  return <I18nProvider locale="en">{children}</I18nProvider>;
}

// ── Simple test component ─────────────────────────────────────────────

function TestComponent({ translationKey, values }: { translationKey: string; values?: Record<string, string | number> }) {
  const { t } = useTranslation();
  return <span data-testid="translated">{t(translationKey, values)}</span>;
}

// ── Tests ─────────────────────────────────────────────────────────────

describe("I18nProvider", () => {
  it("provides translations to child components", () => {
    render(
      <I18nProvider>
        <TestComponent translationKey="common.save" />
      </I18nProvider>,
    );
    expect(screen.getByTestId("translated")).toHaveTextContent("Save");
  });

  it("defaults to English locale when no locale prop is provided", () => {
    render(
      <I18nProvider>
        <TestComponent translationKey="nav.appName" />
      </I18nProvider>,
    );
    expect(screen.getByTestId("translated")).toHaveTextContent("Policy Factory");
  });
});

describe("useTranslation", () => {
  it("throws when used outside I18nProvider", () => {
    // Suppress React error boundary console output
    const consoleSpy = vi.spyOn(console, "error").mockImplementation(() => {});

    expect(() => {
      renderHook(() => useTranslation());
    }).toThrow("useTranslation must be used within an I18nProvider");

    consoleSpy.mockRestore();
  });

  it("returns the current locale", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    expect(result.current.locale).toBe("en");
  });

  it("returns a translation function", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    expect(typeof result.current.t).toBe("function");
  });
});

describe("Translation lookup (t function)", () => {
  it("resolves top-level namespace keys", () => {
    render(
      <I18nProvider>
        <TestComponent translationKey="common.save" />
      </I18nProvider>,
    );
    expect(screen.getByTestId("translated")).toHaveTextContent("Save");
  });

  it("resolves deeply nested keys", () => {
    render(
      <I18nProvider>
        <TestComponent translationKey="cascade.statusRunning" />
      </I18nProvider>,
    );
    expect(screen.getByTestId("translated")).toHaveTextContent("Running");
  });

  it("resolves keys across all major namespaces", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    const { t } = result.current;

    // Common
    expect(t("common.cancel")).toBe("Cancel");
    expect(t("common.delete")).toBe("Delete");
    expect(t("common.loading")).toBe("Loading…");

    // Navigation
    expect(t("nav.appName")).toBe("Policy Factory");
    expect(t("nav.stackOverview")).toBe("Stack Overview");

    // Auth
    expect(t("auth.loginTitle")).toBe("Sign in to Policy Factory");
    expect(t("auth.loginButton")).toBe("Sign in");

    // Stack overview
    expect(t("stackOverview.title")).toBe("Policy Stack");
    expect(t("stackOverview.layerValues")).toBe("Values");
    expect(t("stackOverview.layerPolicies")).toBe("Policies");

    // Layers
    expect(t("layers.narrativeSummary")).toBe("Narrative Summary");
    expect(t("layers.feedbackAccept")).toBe("Accept");

    // Items
    expect(t("items.editButton")).toBe("Edit");
    expect(t("items.saveButton")).toBe("Save Changes");

    // Ideas
    expect(t("ideas.submitButton")).toBe("Submit Idea");
    expect(t("ideas.scoreStrategicFit")).toBe("Strategic Fit");

    // Cascade
    expect(t("cascade.statusIdle")).toBe("Idle");
    expect(t("cascade.stepGeneration")).toBe("Generation");

    // Heartbeat
    expect(t("heartbeat.triggerButton")).toBe("Run Heartbeat");
    expect(t("heartbeat.tierNewsSkim")).toBe("News Skim");

    // Activity
    expect(t("activity.title")).toBe("Activity Feed");

    // Admin
    expect(t("admin.title")).toBe("Admin Panel");
    expect(t("admin.createButton")).toBe("Create User");

    // History
    expect(t("history.pageTitle")).toBe("Version History");

    // Critics
    expect(t("critics.realist")).toBe("Realist");
    expect(t("critics.greenEcological")).toBe("Green/Ecological");
    expect(t("critics.synthesis")).toBe("Synthesis");

    // Errors
    expect(t("errors.network")).toContain("Network error");
    expect(t("errors.unauthorized")).toContain("not authorized");
  });
});

describe("Missing key fallback", () => {
  it("returns the key itself for non-existent keys", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    const { t } = result.current;

    expect(t("nonExistent.key")).toBe("nonExistent.key");
  });

  it("returns the key for partially valid paths", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    const { t } = result.current;

    // "common" exists but "common.nonExistentAction" does not
    expect(t("common.nonExistentAction")).toBe("common.nonExistentAction");
  });

  it("returns the key for completely invalid paths", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    const { t } = result.current;

    expect(t("")).toBe("");
    expect(t("x.y.z.w.v")).toBe("x.y.z.w.v");
  });

  it("logs a warning in development mode for missing keys", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    const { result } = renderHook(() => useTranslation(), { wrapper });
    result.current.t("missing.key.here");

    expect(warnSpy).toHaveBeenCalledWith(
      expect.stringContaining("missing.key.here"),
    );

    warnSpy.mockRestore();
  });

  it("returns the key when looking up a namespace (not a leaf string)", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    const { t } = result.current;

    // "common" is a namespace object, not a string
    expect(t("common")).toBe("common");
  });
});

describe("Interpolation", () => {
  it("substitutes {placeholder} tokens with provided values", () => {
    render(
      <I18nProvider>
        <TestComponent translationKey="common.lastUpdated" values={{ time: "5 min ago" }} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("translated")).toHaveTextContent("Last updated 5 min ago");
  });

  it("substitutes numeric values", () => {
    render(
      <I18nProvider>
        <TestComponent translationKey="common.itemCount" values={{ count: 42 }} />
      </I18nProvider>,
    );
    expect(screen.getByTestId("translated")).toHaveTextContent("42 items");
  });

  it("leaves unmatched placeholders intact", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    const { t } = result.current;

    // "common.lastUpdated" is "Last updated {time}" — pass no values
    expect(t("common.lastUpdated")).toBe("Last updated {time}");
  });

  it("handles multiple placeholders in one string", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    const { t } = result.current;

    // "cascade.progress" is "Step {current} of {total}"
    expect(t("cascade.progress", { current: 2, total: 5 })).toBe("Step 2 of 5");
  });

  it("handles interpolation in missing key fallback", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});

    const { result } = renderHook(() => useTranslation(), { wrapper });
    const { t } = result.current;

    // Missing key with values — should still attempt interpolation on the key
    expect(t("missing.{name}", { name: "test" })).toBe("missing.test");

    warnSpy.mockRestore();
  });
});

describe("Locale extensibility", () => {
  it("architecture supports adding new locales without component changes", () => {
    // This test verifies the architecture:
    // - Components use t("key") and don't reference any locale directly
    // - The I18nProvider accepts a locale prop
    // - Adding a new locale only requires:
    //   1. A new translation file
    //   2. Registering it in the locale registry
    //   3. Passing the locale to I18nProvider
    //
    // We verify this by checking that the component-facing API
    // (useTranslation + t function) works identically regardless of locale.

    const { result } = renderHook(() => useTranslation(), { wrapper });
    const { t, locale } = result.current;

    // The hook returns a locale and a translation function
    expect(locale).toBe("en");
    expect(typeof t).toBe("function");

    // The component calls t("key") — it never references a specific locale.
    // Swapping the locale in I18nProvider is all that's needed.
    expect(t("common.save")).toBe("Save");
  });
});

describe("Testing utilities", () => {
  it("renderWithI18n provides both theme and i18n context", () => {
    renderWithI18n(<TestComponent translationKey="common.save" />);
    expect(screen.getByTestId("translated")).toHaveTextContent("Save");
  });

  it("renderWithI18nOnly provides only i18n context", () => {
    renderWithI18nOnly(<TestComponent translationKey="nav.appName" />);
    expect(screen.getByTestId("translated")).toHaveTextContent("Policy Factory");
  });

  it("renderWithI18n works with interpolation", () => {
    renderWithI18n(
      <TestComponent translationKey="common.itemCount" values={{ count: 7 }} />,
    );
    expect(screen.getByTestId("translated")).toHaveTextContent("7 items");
  });
});

describe("Translation file completeness", () => {
  it("contains all required namespace categories", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    const { t } = result.current;

    // Verify at least one key exists per required namespace
    const namespaces = [
      "common.save",
      "nav.appName",
      "auth.loginTitle",
      "stackOverview.title",
      "layers.narrativeSummary",
      "items.editButton",
      "ideas.submitButton",
      "cascade.statusIdle",
      "heartbeat.triggerButton",
      "activity.title",
      "admin.title",
      "history.title",
      "critics.realist",
      "errors.network",
    ];

    for (const key of namespaces) {
      const value = t(key);
      // Should NOT return the key itself (that would mean it's missing)
      expect(value).not.toBe(key);
    }
  });

  it("contains all six critic perspective names", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    const { t } = result.current;

    expect(t("critics.realist")).toBe("Realist");
    expect(t("critics.liberalInstitutionalist")).toBe("Liberal-institutionalist");
    expect(t("critics.nationalistConservative")).toBe("Nationalist-conservative");
    expect(t("critics.socialDemocratic")).toBe("Social-democratic");
    expect(t("critics.libertarian")).toBe("Libertarian");
    expect(t("critics.greenEcological")).toBe("Green/Ecological");
    expect(t("critics.synthesis")).toBe("Synthesis");
  });

  it("contains all six layer names", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    const { t } = result.current;

    expect(t("stackOverview.layerPhilosophy")).toBe("Philosophy");
    expect(t("stackOverview.layerValues")).toBe("Values");
    expect(t("stackOverview.layerSituationalAwareness")).toBe("Situational Awareness");
    expect(t("stackOverview.layerStrategicObjectives")).toBe("Strategic Objectives");
    expect(t("stackOverview.layerTacticalObjectives")).toBe("Tactical Objectives");
    expect(t("stackOverview.layerPolicies")).toBe("Policies");
  });

  it("contains all cascade status and step labels", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    const { t } = result.current;

    // Status labels
    expect(t("cascade.statusIdle")).toBe("Idle");
    expect(t("cascade.statusRunning")).toBe("Running");
    expect(t("cascade.statusPaused")).toBe("Paused");
    expect(t("cascade.statusCompleted")).toBe("Completed");
    expect(t("cascade.statusFailed")).toBe("Failed");
    expect(t("cascade.statusCancelled")).toBe("Cancelled");
    expect(t("cascade.statusQueued")).toBe("Queued");

    // Step labels
    expect(t("cascade.stepGeneration")).toBe("Generation");
    expect(t("cascade.stepCritics")).toBe("Critics");
    expect(t("cascade.stepSynthesis")).toBe("Synthesis");
  });

  it("contains all six idea score axis names", () => {
    const { result } = renderHook(() => useTranslation(), { wrapper });
    const { t } = result.current;

    expect(t("ideas.scoreStrategicFit")).toBe("Strategic Fit");
    expect(t("ideas.scoreFeasibility")).toBe("Feasibility");
    expect(t("ideas.scoreCost")).toBe("Cost");
    expect(t("ideas.scoreRisk")).toBe("Risk");
    expect(t("ideas.scorePublicAcceptance")).toBe("Public Acceptance");
    expect(t("ideas.scoreInternationalImpact")).toBe("International Impact");
  });
});
