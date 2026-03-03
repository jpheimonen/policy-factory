/**
 * Design token system for Policy Factory.
 *
 * Two complete theme objects (dark and light) share the same TypeScript type.
 * Linear/Notion-inspired aesthetic: subtle borders, generous spacing, Inter font.
 *
 * Layer identity colors provide instant visual identification of the five
 * policy layers throughout the UI.
 */

// ---------------------------------------------------------------------------
// Theme type definition — shared by both dark and light themes
// ---------------------------------------------------------------------------

interface StatusColors {
  bg: string;
  border: string;
  text: string;
}

interface LayerColors {
  primary: string;
  bg: string;
  text: string;
}

export interface Theme {
  colors: {
    bg: {
      primary: string;
      secondary: string;
      tertiary: string;
      elevated: string;
    };
    text: {
      primary: string;
      secondary: string;
      muted: string;
    };
    border: {
      default: string;
      subtle: string;
    };
    accent: {
      blue: string;
      green: string;
      red: string;
      yellow: string;
      orange: string;
      purple: string;
      cyan: string;
    };
    status: {
      active: StatusColors;
      success: StatusColors;
      warning: StatusColors;
      error: StatusColors;
      pending: StatusColors;
    };
    layers: {
      values: LayerColors;
      "situational-awareness": LayerColors;
      "strategic-objectives": LayerColors;
      "tactical-objectives": LayerColors;
      policies: LayerColors;
    };
  };
  fonts: {
    sans: string;
    mono: string;
  };
  fontSizes: {
    xs: string;
    sm: string;
    md: string;
    base: string;
    lg: string;
    xl: string;
  };
  spacing: {
    xs: string;
    sm: string;
    md: string;
    lg: string;
    xl: string;
    xxl: string;
  };
  radii: {
    sm: string;
    md: string;
    lg: string;
    xl: string;
  };
  shadows: {
    sm: string;
    md: string;
    lg: string;
  };
  zIndices: {
    dropdown: number;
    sticky: number;
    modal: number;
    tooltip: number;
  };
  transitions: {
    fast: string;
    normal: string;
    slow: string;
  };
}

// ---------------------------------------------------------------------------
// Shared token values (identical in both themes)
// ---------------------------------------------------------------------------

const fonts: Theme["fonts"] = {
  sans: "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', sans-serif",
  mono: "'JetBrains Mono', 'Fira Code', 'Cascadia Code', 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace",
};

const fontSizes: Theme["fontSizes"] = {
  xs: "0.75rem",   // 12px
  sm: "0.8125rem", // 13px
  md: "0.875rem",  // 14px
  base: "1rem",    // 16px
  lg: "1.125rem",  // 18px
  xl: "1.25rem",   // 20px
};

const spacing: Theme["spacing"] = {
  xs: "4px",
  sm: "8px",
  md: "12px",
  lg: "16px",
  xl: "24px",
  xxl: "32px",
};

const radii: Theme["radii"] = {
  sm: "4px",
  md: "6px",
  lg: "8px",
  xl: "12px",
};

const zIndices: Theme["zIndices"] = {
  dropdown: 100,
  sticky: 200,
  modal: 300,
  tooltip: 400,
};

const transitions: Theme["transitions"] = {
  fast: "0.15s ease",
  normal: "0.2s ease",
  slow: "0.3s ease",
};

// ---------------------------------------------------------------------------
// Dark theme
// ---------------------------------------------------------------------------

export const darkTheme: Theme = {
  colors: {
    bg: {
      primary: "#0a0a0c",
      secondary: "#111114",
      tertiary: "#18181c",
      elevated: "#1e1e24",
    },
    text: {
      primary: "#ebebef",
      secondary: "#a0a0b0",
      muted: "#6b6b80",
    },
    border: {
      default: "rgba(255, 255, 255, 0.08)",
      subtle: "rgba(255, 255, 255, 0.04)",
    },
    accent: {
      blue: "#4c8dff",
      green: "#3ecf8e",
      red: "#ef4444",
      yellow: "#f5a623",
      orange: "#f97316",
      purple: "#a855f7",
      cyan: "#22d3ee",
    },
    status: {
      active: {
        bg: "rgba(76, 141, 255, 0.12)",
        border: "rgba(76, 141, 255, 0.24)",
        text: "#4c8dff",
      },
      success: {
        bg: "rgba(62, 207, 142, 0.12)",
        border: "rgba(62, 207, 142, 0.24)",
        text: "#3ecf8e",
      },
      warning: {
        bg: "rgba(245, 166, 35, 0.12)",
        border: "rgba(245, 166, 35, 0.24)",
        text: "#f5a623",
      },
      error: {
        bg: "rgba(239, 68, 68, 0.12)",
        border: "rgba(239, 68, 68, 0.24)",
        text: "#ef4444",
      },
      pending: {
        bg: "rgba(107, 107, 128, 0.12)",
        border: "rgba(107, 107, 128, 0.24)",
        text: "#8b8ba0",
      },
    },
    layers: {
      values: {
        primary: "#a855f7",
        bg: "rgba(168, 85, 247, 0.12)",
        text: "#c084fc",
      },
      "situational-awareness": {
        primary: "#22d3ee",
        bg: "rgba(34, 211, 238, 0.12)",
        text: "#67e8f9",
      },
      "strategic-objectives": {
        primary: "#4c8dff",
        bg: "rgba(76, 141, 255, 0.12)",
        text: "#7cb0ff",
      },
      "tactical-objectives": {
        primary: "#f5a623",
        bg: "rgba(245, 166, 35, 0.12)",
        text: "#f7c065",
      },
      policies: {
        primary: "#3ecf8e",
        bg: "rgba(62, 207, 142, 0.12)",
        text: "#6ee7b7",
      },
    },
  },
  fonts,
  fontSizes,
  spacing,
  radii,
  shadows: {
    sm: "0 1px 2px rgba(0, 0, 0, 0.3)",
    md: "0 4px 12px rgba(0, 0, 0, 0.4)",
    lg: "0 8px 24px rgba(0, 0, 0, 0.5)",
  },
  zIndices,
  transitions,
};

// ---------------------------------------------------------------------------
// Light theme
// ---------------------------------------------------------------------------

export const lightTheme: Theme = {
  colors: {
    bg: {
      primary: "#ffffff",
      secondary: "#f8f8fa",
      tertiary: "#f0f0f4",
      elevated: "#ffffff",
    },
    text: {
      primary: "#1a1a2e",
      secondary: "#5a5a72",
      muted: "#9090a8",
    },
    border: {
      default: "rgba(0, 0, 0, 0.08)",
      subtle: "rgba(0, 0, 0, 0.04)",
    },
    accent: {
      blue: "#2563eb",
      green: "#16a34a",
      red: "#dc2626",
      yellow: "#d97706",
      orange: "#ea580c",
      purple: "#7c3aed",
      cyan: "#0891b2",
    },
    status: {
      active: {
        bg: "rgba(37, 99, 235, 0.08)",
        border: "rgba(37, 99, 235, 0.2)",
        text: "#2563eb",
      },
      success: {
        bg: "rgba(22, 163, 74, 0.08)",
        border: "rgba(22, 163, 74, 0.2)",
        text: "#16a34a",
      },
      warning: {
        bg: "rgba(217, 119, 6, 0.08)",
        border: "rgba(217, 119, 6, 0.2)",
        text: "#d97706",
      },
      error: {
        bg: "rgba(220, 38, 38, 0.08)",
        border: "rgba(220, 38, 38, 0.2)",
        text: "#dc2626",
      },
      pending: {
        bg: "rgba(144, 144, 168, 0.08)",
        border: "rgba(144, 144, 168, 0.2)",
        text: "#6b6b80",
      },
    },
    layers: {
      values: {
        primary: "#7c3aed",
        bg: "rgba(124, 58, 237, 0.08)",
        text: "#6d28d9",
      },
      "situational-awareness": {
        primary: "#0891b2",
        bg: "rgba(8, 145, 178, 0.08)",
        text: "#0e7490",
      },
      "strategic-objectives": {
        primary: "#2563eb",
        bg: "rgba(37, 99, 235, 0.08)",
        text: "#1d4ed8",
      },
      "tactical-objectives": {
        primary: "#d97706",
        bg: "rgba(217, 119, 6, 0.08)",
        text: "#b45309",
      },
      policies: {
        primary: "#16a34a",
        bg: "rgba(22, 163, 74, 0.08)",
        text: "#15803d",
      },
    },
  },
  fonts,
  fontSizes,
  spacing,
  radii,
  shadows: {
    sm: "0 1px 3px rgba(0, 0, 0, 0.06)",
    md: "0 4px 12px rgba(0, 0, 0, 0.08)",
    lg: "0 8px 24px rgba(0, 0, 0, 0.12)",
  },
  zIndices,
  transitions,
};
