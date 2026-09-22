// ============================================================================
// src/LanguageContext.js
//
// WHAT THIS FILE DOES (in plain words):
// Exactly the same job as the web app's lib/LanguageContext.tsx: remembers
// whether the app is showing Nepali or English right now, and gives every
// screen a way to read the current phrase book and flip the language.
// ============================================================================

import { createContext, useContext, useState } from "react";
import { dictionaries } from "./i18n";

const LanguageContext = createContext(undefined);

// Wrap the whole app in this component (done once, in App.js) so every
// screen inside it can ask "what language are we in right now?"
export function LanguageProvider({ children }) {
  // Opens in Nepali by default, same as the web app - Nepali is the
  // primary language, English is an optional toggle.
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

// Any screen calls this to get the current phrase book and the toggle
// function:
//   const { text, toggleLanguage } = useLanguage();
export function useLanguage() {
  const context = useContext(LanguageContext);
  if (!context) {
    throw new Error("useLanguage must be used inside a <LanguageProvider>");
  }
  return context;
}
