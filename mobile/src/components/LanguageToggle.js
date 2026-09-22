// ============================================================================
// src/components/LanguageToggle.js
//
// WHAT THIS FILE DOES (in plain words):
// Same job as the web app's LanguageToggle.jsx: the small pill button that
// switches the whole app between Nepali and English when tapped.
// ============================================================================

import { Pressable, Text, StyleSheet } from "react-native";
import { useLanguage } from "../LanguageContext";
import { theme } from "../theme";

export default function LanguageToggle() {
  const { text, toggleLanguage } = useLanguage();

  return (
    <Pressable
      onPress={toggleLanguage}
      accessibilityLabel="Switch language / भाषा बदल्नुहोस्"
      style={styles.button}
    >
      <Text style={styles.label}>{text.toggleButtonLabel}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  button: {
    paddingVertical: 10,
    paddingHorizontal: 20,
    borderRadius: 999,
    borderWidth: 2,
    borderColor: theme.colors.surface,
    backgroundColor: "rgba(255, 255, 255, 0.25)",
  },
  label: {
    color: theme.colors.surface,
    fontSize: 16,
    fontWeight: "600",
  },
});
