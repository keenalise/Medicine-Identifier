// ============================================================================
// src/screens/HomeScreen.js
//
// WHAT THIS FILE DOES (in plain words):
// The mobile equivalent of the web app's app/page.jsx: the first screen
// the user sees, showing the bright header + language toggle, and then
// one of four things, same as the web app:
//   1. The camera (default).
//   2. A "identifying..." message while the photo is uploaded to the
//      backend and analysed.
//   3. The result: the photo, the medicine's name, what it's for, and the
//      expiry date, with big ✅ / ❌ buttons so the user confirms it.
//   4. An error message with a "try again" button if the backend could
//      not be reached.
//
// The barcode is NOT sent to the backend separately: the backend reads
// barcodes out of the photo itself (its step 1), so a photo is all it
// ever needs. CameraCapture takes a photo the moment it sees a barcode.
// ============================================================================

import { useState } from "react";
import { View, Text, Image, Pressable, StyleSheet, ScrollView } from "react-native";
import { LinearGradient } from "expo-linear-gradient";
import CameraCapture from "../components/CameraCapture";
import LanguageToggle from "../components/LanguageToggle";
import { useLanguage } from "../LanguageContext";
import { theme } from "../theme";
import { scanPhoto } from "../api";
import { BACKEND_URL, BACKEND_URL_IS_GUESS } from "../config";

export default function HomeScreen() {
  const { text, language } = useLanguage();
  // Same shape as the web version:
  //   { type: "none" }                       - camera is showing
  //   { type: "loading", photoUri }          - waiting for the backend
  //   { type: "result", photoUri, data }     - backend responded
  //   { type: "error" }                      - request failed
  const [capture, setCapture] = useState({ type: "none" });

  function handleBarcodeFound(_barcodeText) {
    // Intentionally empty: CameraCapture also takes a photo when it finds
    // a barcode, and that photo (which contains the barcode) is what gets
    // sent to the backend via handlePhotoCaptured below.
  }

  async function handlePhotoCaptured(photoUri) {
    setCapture({ type: "loading", photoUri });
    try {
      const data = await scanPhoto(photoUri);
      setCapture({ type: "result", photoUri, data });
    } catch (error) {
      // Common causes: the backend isn't running, it was started without
      // --host 0.0.0.0 so the phone can't reach it, or the phone is on a
      // different Wi-Fi. Tell the user plainly rather than leaving them
      // staring at a spinner forever.
      console.warn("Scan request failed:", error);
      setCapture({ type: "error" });
    }
  }

  function handleReset() {
    setCapture({ type: "none" });
  }

  function handleConfirmation(wasCorrect) {
    // TODO (future step): send this confirmation/correction back to the
    // backend so it can be logged and used to grow medicine_db.json.
    console.log("User confirmed result was correct:", wasCorrect);
    handleReset();
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

        {capture.type === "loading" && (
          <View style={styles.centered}>
            <Image
              source={{ uri: capture.photoUri }}
              style={styles.capturedPhoto}
              resizeMode="cover"
            />
            <Text style={[styles.bodyText, { marginTop: 20 }]}>
              {text.scanningOcrVision}
            </Text>
          </View>
        )}

        {capture.type === "error" && (
          <View style={styles.centered}>
            <Text style={[styles.bodyText, { color: theme.colors.danger }]}>
              {text.errorGeneric}
            </Text>
            {/* Developer hint, deliberately small: which address was tried.
                The most common failure is the backend not being reachable
                from the phone, and this makes that obvious at a glance. */}
            <Text style={styles.hintText}>
              {BACKEND_URL}
              {BACKEND_URL_IS_GUESS
                ? "\n(could not detect the laptop's address - set BACKEND_URL_OVERRIDE in src/config.js)"
                : ""}
            </Text>
            <ResetButton onPress={handleReset} label={text.tryAgainButton} />
          </View>
        )}

        {capture.type === "result" && (
          <ResultScreen
            photoUri={capture.photoUri}
            data={capture.data}
            text={text}
            language={language}
            onConfirm={() => handleConfirmation(true)}
            onReject={() => handleConfirmation(false)}
          />
        )}
      </ScrollView>
    </View>
  );
}

// The screen shown after the backend responds: the photo, what it found,
// and the big confirm/reject buttons - never presenting a guess as final
// on its own. Mirrors ResultScreen in the web app.
function ResultScreen({ photoUri, data, text, language, onConfirm, onReject }) {
  // Nepali name in Nepali mode, English name in English mode, falling back
  // to whichever one the backend actually provided.
  const nameText =
    language === "en" ? data.generic_name : data.generic_name_ne || data.generic_name;
  // purpose_en is only filled in for medicines from our own database (not
  // when the vision model answered), so fall back to the Nepali text.
  const purposeText =
    language === "en" && data.purpose_en ? data.purpose_en : data.purpose_ne;
  const expiryText = data.expiry_text_ne || data.expiry_raw_text || "?";

  return (
    <View style={styles.centered}>
      <Image source={{ uri: photoUri }} style={styles.capturedPhoto} resizeMode="cover" />

      {data.identified ? (
        <View style={styles.resultBlock}>
          <Text style={styles.resultName}>{nameText}</Text>

          {purposeText ? (
            <Text style={styles.bodyText}>
              {text.resultPurposeLabel} {purposeText}
            </Text>
          ) : null}

          <Text style={[styles.bodyText, { marginTop: 8 }]}>
            {text.resultExpiryLabel} {expiryText}
          </Text>

          <View style={styles.confirmRow}>
            <Pressable
              onPress={onConfirm}
              style={[styles.confirmButton, { backgroundColor: theme.colors.success }]}
            >
              <Text style={styles.confirmButtonLabel}>{text.confirmCorrectButton}</Text>
            </Pressable>
            <Pressable
              onPress={onReject}
              style={[styles.confirmButton, { backgroundColor: theme.colors.danger }]}
            >
              <Text style={styles.confirmButtonLabel}>{text.confirmWrongButton}</Text>
            </Pressable>
          </View>
        </View>
      ) : (
        <View style={styles.resultBlock}>
          <Text style={styles.bodyText}>{text.scanningFailedRetry}</Text>
          <ResetButton onPress={onReject} label={text.tryAgainButton} />
        </View>
      )}
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
  hintText: {
    fontSize: 13,
    color: theme.colors.text,
    opacity: 0.6,
    textAlign: "center",
    marginTop: 12,
  },
  capturedPhoto: {
    width: "100%",
    aspectRatio: 3 / 4,
    borderRadius: theme.radiusLarge,
  },
  resultBlock: {
    width: "100%",
    alignItems: "center",
    marginTop: 20,
  },
  resultName: {
    fontSize: theme.fontSize.heading,
    fontWeight: "700",
    color: theme.colors.text,
    textAlign: "center",
    marginBottom: 8,
  },
  confirmRow: {
    flexDirection: "row",
    gap: 16,
    justifyContent: "center",
    marginTop: 24,
  },
  confirmButton: {
    minHeight: theme.touchTargetMin,
    paddingHorizontal: 28,
    borderRadius: theme.radiusLarge,
    alignItems: "center",
    justifyContent: "center",
  },
  confirmButtonLabel: {
    color: theme.colors.textOnPrimary,
    fontSize: theme.fontSize.button,
    fontWeight: "700",
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
