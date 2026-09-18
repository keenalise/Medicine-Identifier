"use client";

// ============================================================================
// lib/LanguageContext.jsx
//
// WHAT THIS FILE DOES (in plain words):
// This keeps track of ONE thing: "is the app currently showing Nepali or
// English text?" It also gives every screen a way to:
//   1. Read the current language.
//   2. Read the correct phrase book (see lib/i18n.js) for that language.
//   3. Flip the language when the user taps the toggle button.
//
// Think of it like a single light switch that every room (every screen) in
// the app can see and flip. Without this, each screen would need its own
// separate switch, and they could easily get out of sync with each other.
// ============================================================================

import { createContext, useContext, useState } from "react";
import { dictionaries } from "./i18n";

const LanguageContext = createContext(undefined);

// Wrap the whole app in this component (done once, in app/layout.jsx) so
// every screen inside it can ask "what language are we in right now?"
export function LanguageProvider({ children }) {
  // The app OPENS in Nepali by default, per the project requirement that
  // Nepali is the primary language and English is an optional toggle.
  const [language, setLanguage] = useState("ne");

  function toggleLanguage() {
    setLanguage((current) => (current === "ne" ? "en" : "ne"));
  }

  const value = {
    language,
    text: dictionaries[language],
    toggleLanguage,
  };

  return (
    <LanguageContext.Provider value={value}>
      {children}
    </LanguageContext.Provider>
  );
}

// Any screen or component calls this one line to get the current phrase
// book and the toggle function:
//   const { text, toggleLanguage } = useLanguage();
//   <button onClick={toggleLanguage}>{text.toggleButtonLabel}</button>
export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used inside a <LanguageProvider>");
  }
  return context;
}
