"use client";

// ============================================================================
// components/LanguageToggle.jsx
//
// WHAT THIS FILE DOES (in plain words):
// This is the small button (usually placed top-right) that a user taps to
// switch the whole app between Nepali and English. It doesn't hold any
// language logic itself - it just displays the button and, when tapped,
// tells the LanguageContext (lib/LanguageContext.jsx) to flip the switch.
// ============================================================================

import { useLanguage } from "../lib/LanguageContext";

export default function LanguageToggle() {
  const { text, toggleLanguage } = useLanguage();

  return (
    <button
      onClick={toggleLanguage}
      aria-label="Switch language / भाषा बदल्नुहोस्"
      style={{
        padding: "10px 20px",
        borderRadius: "999px",
        border: "2px solid var(--color-surface)",
        background: "rgba(255, 255, 255, 0.25)",
        color: "var(--color-surface)",
        fontSize: "18px",
        fontWeight: 600,
      }}
    >
      {text.toggleButtonLabel}
    </button>
  );
}
