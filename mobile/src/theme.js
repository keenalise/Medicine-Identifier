// ============================================================================
// src/theme.js
//
// WHAT THIS FILE DOES (in plain words):
// Same job as the web app's app/globals.css: one place that defines every
// color and font size used across the app, so changing a color here
// updates it everywhere.
//
// React Native doesn't support CSS (or CSS variables like the web version
// used), so instead this is a plain JavaScript object that every component
// imports and reads values from, e.g. `theme.colors.primary`.
//
// The VALUES here are kept identical to the web app's globals.css, so the
// mobile app looks and feels like the same product, not a different one.
// ============================================================================

export const theme = {
  colors: {
    heroStart: "#FF9F1C",
    heroEnd: "#FFB703",
    surface: "#FFFDF7",
    primary: "#0B6E4F",
    primaryPressed: "#084D38",
    danger: "#D62828",
    dangerSurface: "#FDEAEA",
    success: "#2A9134",
    successSurface: "#EAF7EC",
    text: "#1B263B",
    textOnPrimary: "#FFFFFF",
  },

  fontSize: {
    body: 22,
    heading: 30,
    button: 24,
    label: 18,
  },

  // React Native has no built-in "minimum touch target" concept like CSS
  // does - we just apply this number directly as minHeight/minWidth on
  // buttons, so older users can tap them accurately.
  touchTargetMin: 64,
  radiusLarge: 28,
};
