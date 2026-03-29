/**
 * Shared layer and critic constants.
 *
 * Provides i18n key mappings for layer display names and critic
 * archetype display names, used across pages and components.
 */

/** Maps layer slugs to their i18n translation keys. */
export const LAYER_NAME_KEYS: Record<string, string> = {
  philosophy: "stackOverview.layerPhilosophy",
  values: "stackOverview.layerValues",
  "situational-awareness": "stackOverview.layerSituationalAwareness",
  "strategic-objectives": "stackOverview.layerStrategicObjectives",
  "tactical-objectives": "stackOverview.layerTacticalObjectives",
  policies: "stackOverview.layerPolicies",
};

/** Maps critic archetype slugs to their i18n translation keys. */
export const CRITIC_DISPLAY_KEYS: Record<string, string> = {
  realist: "critics.realist",
  "liberal-institutionalist": "critics.liberalInstitutionalist",
  "nationalist-conservative": "critics.nationalistConservative",
  "social-democratic": "critics.socialDemocratic",
  libertarian: "critics.libertarian",
  "green-ecological": "critics.greenEcological",
};

/** Critic archetypes in canonical display order. */
export const CRITIC_ORDER = [
  "realist",
  "liberal-institutionalist",
  "nationalist-conservative",
  "social-democratic",
  "libertarian",
  "green-ecological",
];
