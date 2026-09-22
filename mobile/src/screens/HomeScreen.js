// ============================================================================
// src/screens/HomeScreen.js
//
// WHAT THIS FILE DOES (in plain words):
// The mobile equivalent of the web app's app/page.jsx: the first screen
// the user sees, showing the bright header + language toggle, and either
// the camera (default) or a placeholder "captured!" screen after a photo
// is taken / barcode found.
//
// Same TODO as the web version: the backend call isn't wired up yet.
// ============================================================================

import { useState } from "react";
import { View, Text, Image, Pressable, StyleSheet, ScrollView } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import CameraCapture from "../components/CameraCapture";
import LanguageToggle from "../components/LanguageToggle";
import { useLanguage } from "../LanguageContext";
import { theme } from "../theme";

export default function HomeScreen() {
  const { text } = useLanguage();
  // Same shape as the web version: { type: "none" } | { type: "barcode", value }
  // | { type: "photo", photoUri }
  const [capture, setCapture] = useState({ type: "none" });

  function handleBarcodeFound(barcodeText) {
    // TODO (backend step): send `barcodeText` to the backend's /scan
    // endpoint. Placeholder for now, same as the web app at this stage.
    setCapture({ type: "barcode", value: barcodeText });
  }

  function handlePhotoCaptured(photoUri) {
    // TODO (backend step): upload the photo at `photoUri` to the
    // backend's /scan endpoint. Placeholder for now.
    setCapture({ type: "photo", photoUri });
  }

  function handleReset() {
    setCapture({ type: "none" });
  }

  return (
    <View style={styles.screen}>
      <LinearGradient
        colors={[theme.colors.heroStart, theme.colors.heroEnd]}
        start={{ x: 0, y: 0 }}
        end={{ x: 1, y: 1 }}
        style={styles.header}
      >
        <Text style={styles.headerTitle}>{text.appName}</Text>
        <LanguageToggle />
      </LinearGradient>

      <ScrollView contentContainerStyle={styles.content}>
        {capture.type === "none" && (
          <>
            <Text style={styles.heading}>{text.homeHeading}</Text>
            <Text style={styles.subheading}>{text.homeSubheading}</Text>
            <CameraCapture
              onBarcodeFound={handleBarcodeFound}
              onPhotoCaptured={handlePhotoCaptured}
            />
          </>
        )}

        {capture.type === "barcode" && (
          <View style={styles.centered}>
            <Text style={styles.bodyText}>
              {/* Placeholder until the backend lookup exists */}
              Barcode captured: {capture.value}
            </Text>
            <ResetButton onPress={handleReset} label={text.tryAgainButton} />
          </View>
        )}

        {capture.type === "photo" && (
          <View style={styles.centered}>
            <Image
              source={{ uri: capture.photoUri }}
              style={styles.capturedPhoto}
              resizeMode="cover"
            />
            <ResetButton onPress={handleReset} label={text.tryAgainButton} />
          </View>
        )}
      </ScrollView>
    </View>
  );
}

// Small reusable "try again" button - matches the web app's ResetButton.
function ResetButton({ onPress, label }) {
  return (
    <Pressable style={styles.resetButton} onPress={onPress}>
      <Text style={styles.resetButtonLabel}>{label}</Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: theme.colors.surface,
  },
  header: {
    paddingTop: 56, // extra space for the phone's status bar / notch
    paddingBottom: 20,
    paddingHorizontal: 20,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  headerTitle: {
    color: theme.colors.textOnPrimary,
    fontSize: theme.fontSize.heading,
    fontWeight: "700",
  },
  content: {
    padding: 20,
    alignItems: "center",
  },
  heading: {
    fontSize: theme.fontSize.heading,
    fontWeight: "700",
    color: theme.colors.text,
    textAlign: "center",
  },
  subheading: {
    fontSize: theme.fontSize.label,
    color: theme.colors.text,
    textAlign: "center",
    marginTop: 8,
    marginBottom: 24,
  },
  centered: {
    width: "100%",
    alignItems: "center",
  },
  bodyText: {
    fontSize: theme.fontSize.body,
    color: theme.colors.text,
    textAlign: "center",
  },
  capturedPhoto: {
    width: "100%",
    aspectRatio: 3 / 4,
    borderRadius: theme.radiusLarge,
  },
  resetButton: {
    marginTop: 20,
    minHeight: theme.touchTargetMin,
    paddingHorizontal: 32,
    borderRadius: theme.radiusLarge,
    borderWidth: 3,
    borderColor: theme.colors.primary,
    backgroundColor: theme.colors.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  resetButtonLabel: {
    color: theme.colors.primary,
    fontSize: theme.fontSize.button,
    fontWeight: "700",
  },
});
