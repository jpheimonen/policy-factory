/**
 * English translation file.
 *
 * This is the canonical list of all UI strings in Policy Factory.
 * Components never contain raw display text — they always reference
 * a key from this file via the useTranslation hook.
 *
 * Keys use a flat dot-notation namespace organized by page/feature area.
 * To add a new locale, create a new file (e.g., fi.ts) with the same
 * structure and register it in the i18n provider.
 */

const en = {
  // ── Common ──────────────────────────────────────────────────────────
  common: {
    save: "Save",
    cancel: "Cancel",
    delete: "Delete",
    confirm: "Confirm",
    close: "Close",
    back: "Back",
    refresh: "Refresh",
    submit: "Submit",
    edit: "Edit",
    create: "Create",
    loading: "Loading…",
    error: "Error",
    success: "Success",
    noItems: "No items to display",
    emptyState: "Nothing here yet",
    lastUpdated: "Last updated {time}",
    itemCount: "{count} items",
    search: "Search",
    filter: "Filter",
    sort: "Sort",
    actions: "Actions",
    yes: "Yes",
    no: "No",
    comingSoon: "Coming soon",
    initializing: "Initializing…",
  },

  // ── Navigation ──────────────────────────────────────────────────────
  nav: {
    appName: "Policy Factory",
    home: "Home",
    stackOverview: "Stack Overview",
    ideas: "Ideas",
    cascade: "Cascade",
    activity: "Activity",
    admin: "Admin",
    versionHistory: "Version History",
    logout: "Log out",
    settings: "Settings",
    cascadeStatusIdle: "Idle",
    cascadeStatusRunning: "Cascade running",
    cascadeStatusPaused: "Cascade paused",
    cascadeStatusFailed: "Cascade failed",
    cascadeProcessing: "Processing {layer}",
  },

  // ── Authentication ──────────────────────────────────────────────────
  auth: {
    loginTitle: "Sign in to Policy Factory",
    emailLabel: "Email",
    emailPlaceholder: "you@example.com",
    passwordLabel: "Password",
    loginButton: "Sign in",
    registerTitle: "Create your account",
    registerDescription: "Set up the first admin account to get started.",
    registerButton: "Create account",
    confirmPasswordLabel: "Confirm password",
    loggingIn: "Signing in…",
    registering: "Creating account…",
    errorInvalidCredentials: "Invalid email or password",
    errorSessionExpired: "Your session has expired. Please sign in again.",
    errorPasswordMismatch: "Passwords do not match",
    errorEmailRequired: "Email is required",
    errorEmailInvalid: "Please enter a valid email address",
    errorPasswordRequired: "Password is required",
    errorRegistrationClosed: "Registration is closed. Contact an admin.",
  },

  // ── Stack Overview (Home) ───────────────────────────────────────────
  stackOverview: {
    title: "Policy Stack",
    layerValues: "Values",
    layerSituationalAwareness: "Situational Awareness",
    layerStrategicObjectives: "Strategic Objectives",
    layerTacticalObjectives: "Tactical Objectives",
    layerPolicies: "Policies",
    itemCount: "{count} items",
    noItems: "No items",
    lastUpdated: "Updated {time}",
    neverUpdated: "Not updated yet",
    feedbackMemoCount: "{count} pending memos",
    inputPlaceholder: "Submit new information or input…",
    submitButton: "Submit",
    cascadeRunning: "Cascade running",
    cascadeIdle: "System idle",
    loadError: "Failed to load layer data",
    retryButton: "Retry",
    noNarrativeSummary: "No narrative summary yet",
  },

  // ── Layers ──────────────────────────────────────────────────────────
  layers: {
    narrativeSummary: "Narrative Summary",
    items: "Items",
    refreshButton: "Refresh Layer",
    refreshConfirm: "This will regenerate the layer and trigger a cascade. Continue?",
    feedbackMemos: "Feedback Memos",
    feedbackAccept: "Accept",
    feedbackDismiss: "Dismiss",
    feedbackEmpty: "No pending feedback memos",
    criticAssessment: "Critic Assessment",
    criticAssessmentEmpty: "No critic assessment available",
    noItems: "No items in this layer yet",
  },

  // ── Items ───────────────────────────────────────────────────────────
  items: {
    editButton: "Edit",
    saveButton: "Save Changes",
    cancelEdit: "Cancel",
    title: "Title",
    status: "Status",
    crossReferences: "Cross-Layer References",
    noCrossReferences: "No cross-layer references",
    lastModifiedBy: "Last modified by {user}",
    lastModifiedAt: "Last modified {time}",
    deleteConfirm: "Are you sure you want to delete this item?",
    createNew: "Create New Item",
    body: "Content",
  },

  // ── Ideas ───────────────────────────────────────────────────────────
  ideas: {
    submitPlaceholder: "Describe your policy idea…",
    submitButton: "Submit Idea",
    generateButton: "Generate Ideas",
    generateScoped: "Generate ideas for this objective",
    statusPending: "Pending",
    statusEvaluating: "Evaluating",
    statusEvaluated: "Evaluated",
    statusArchived: "Archived",
    scoreStrategicFit: "Strategic Fit",
    scoreFeasibility: "Feasibility",
    scoreCost: "Cost",
    scoreRisk: "Risk",
    scorePublicAcceptance: "Public Acceptance",
    scoreInternationalImpact: "International Impact",
    radarTitle: "Evaluation Scores",
    criticAssessments: "Critic Assessments",
    synthesis: "Synthesis",
    overallScore: "Overall Score",
    sortByScore: "Sort by Score",
    sortByRecent: "Most Recent",
    filterByStatus: "Filter by Status",
    noIdeas: "No ideas submitted yet",
    submittedBy: "Submitted by {user}",
    submittedAt: "Submitted {time}",
    evaluationInProgress: "Evaluation in progress…",
  },

  // ── Cascade ─────────────────────────────────────────────────────────
  cascade: {
    statusIdle: "Idle",
    statusRunning: "Running",
    statusPaused: "Paused",
    statusCompleted: "Completed",
    statusFailed: "Failed",
    statusCancelled: "Cancelled",
    statusQueued: "Queued",
    stepGeneration: "Generation",
    stepCritics: "Critics",
    stepSynthesis: "Synthesis",
    resumeButton: "Resume",
    cancelButton: "Cancel Cascade",
    queueHeading: "Cascade Queue",
    queueEmpty: "No cascades queued",
    queuePosition: "Position {position} in queue",
    errorDisplay: "Cascade paused due to error",
    currentAgent: "Running: {agent}",
    processingLayer: "Processing {layer}",
    progress: "Step {current} of {total}",
    triggerSource: "Triggered by {source}",
    noActiveCascade: "No active cascade",
  },

  // ── Heartbeat ───────────────────────────────────────────────────────
  heartbeat: {
    triggerButton: "Run Heartbeat",
    tierNewsSkim: "News Skim",
    tierTriageAnalysis: "Triage Analysis",
    tierSaUpdate: "SA Update",
    tierFullCascade: "Full Cascade",
    logHeading: "Heartbeat Log",
    logEmpty: "No heartbeat runs recorded",
    tierReached: "Reached Tier {tier}",
    nothingNoteworthy: "Nothing noteworthy",
    itemsFlagged: "{count} items flagged",
  },

  // ── Activity ────────────────────────────────────────────────────────
  activity: {
    title: "Activity Feed",
    filterByType: "Filter by Type",
    filterByLayer: "Filter by Layer",
    allTypes: "All Types",
    allLayers: "All Layers",
    eventCascade: "Cascade",
    eventHeartbeat: "Heartbeat",
    eventIdea: "Idea",
    eventUser: "User Action",
    eventSystem: "System",
    noActivity: "No activity recorded",
  },

  // ── Admin ───────────────────────────────────────────────────────────
  admin: {
    title: "Admin Panel",
    userListHeading: "Users",
    createUserHeading: "Create User",
    emailLabel: "Email",
    passwordLabel: "Password",
    roleLabel: "Role",
    roleAdmin: "Admin",
    roleUser: "User",
    createdAt: "Created {time}",
    createButton: "Create User",
    deleteButton: "Delete",
    deleteConfirm: "Are you sure you want to delete user {email}?",
    cannotDeleteSelf: "You cannot delete your own account",
    noUsers: "No users found",
  },

  // ── History ─────────────────────────────────────────────────────────
  history: {
    title: "Version History",
    dateColumn: "Date",
    changeColumn: "Change",
    triggerColumn: "Triggered By",
    noHistory: "No version history available",
  },

  // ── Critics ─────────────────────────────────────────────────────────
  critics: {
    realist: "Realist",
    liberalInstitutionalist: "Liberal-institutionalist",
    nationalistConservative: "Nationalist-conservative",
    socialDemocratic: "Social-democratic",
    libertarian: "Libertarian",
    greenEcological: "Green/Ecological",
    synthesis: "Synthesis",
    agreement: "Agreement",
    disagreement: "Disagreement",
    alternatives: "Alternatives",
    reasoning: "Reasoning",
  },

  // ── Errors ──────────────────────────────────────────────────────────
  errors: {
    network: "Network error. Please check your connection and try again.",
    unauthorized: "You are not authorized. Please sign in.",
    forbidden: "You do not have permission to perform this action.",
    notFound: "The requested resource was not found.",
    serverError: "An unexpected server error occurred. Please try again later.",
    cascadeLockHeld: "A cascade is currently running. Your request has been queued.",
    generic: "Something went wrong. Please try again.",
    validationFailed: "Please check the form for errors.",
    timeout: "The request timed out. Please try again.",
  },
} as const;

export type TranslationKeys = typeof en;
export default en;
