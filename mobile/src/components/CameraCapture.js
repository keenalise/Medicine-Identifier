// ============================================================================
// src/components/CameraCapture.js
//
// WHAT THIS FILE DOES (in plain words):
// The mobile equivalent of the web app's CameraCapture.jsx. Same behavior:
//   - Shows a live camera preview.
//   - Quietly watches for a barcode while the camera is open and reports
//     it through onBarcodeFound (informational only - the backend reads
//     the barcode out of the photo itself).
//   - Takes a photo ONLY when the user taps the "Take Photo" button - no
//     automatic capture, so the user decides when the medicine is lined
//     up and in focus. The photo is handed to onPhotoCaptured, and the
//     home screen sends it to the backend to get the name, purpose and
//     expiry date.
//   - Has a "Choose from Gallery" fallback, always available, even if the
//     camera itself fails to start.
//
// KEY DIFFERENCE FROM THE WEB VERSION: on a phone, the OS itself needs to
// ask the user for camera permission (there's no browser doing that for
// us), so this file also has to handle "permission not yet granted" as
// its own screen state.
//
// WHY THE "CAMERA READY" HANDLING EXISTS:
// expo-camera throws "Failed to capture image" when takePictureAsync is
// called before the camera session has actually started, or in the same
// moment the session is being reconfigured. The earlier version of this
// file did both: it fired an automatic capture 5 s after the component
// mounted (not 5 s after the camera was READY), and it switched the
// barcode scanner off (a prop change that restarts the session) in the
// very same tick as taking the photo. Now the button is disabled until
// onCameraReady fires, camera props never change just before capturing
// (the scanner stays on), and a failed capture is retried once.
// ============================================================================

import { useEffect, useRef, useState } from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImagePicker from "expo-image-picker";
import { useLanguage } from "../LanguageContext";
import { theme } from "../theme";

// A short pause before retrying a failed capture, long enough for the
// camera session to settle on slower phones.
const RETRY_DELAY_MS = 700;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default function CameraCapture({ onBarcodeFound, onPhotoCaptured }) {
  const { text } = useLanguage();

  // A "ref" here is a stable handle to the actual camera component, so we
  // can call functions on it directly (like "take a picture now").
  const cameraRef = useRef(null);

  // expo-camera's permission hook: `permission` tells us the current
  // status (granted / not granted / not asked yet), and
  // `requestPermission` is a function we call to show the OS's permission
  // popup.
  const [permission, requestPermission] = useCameraPermissions();

  // Set by the camera itself once its session is running. Nothing may
  // capture before this is true.
  const [isCameraReady, setIsCameraReady] = useState(false);

  // Once a capture has started, ignore further button taps so we don't
  // take two photos. A ref is used for the actual check (always current,
  // even mid-await), and the state copy is only for showing the right
  // status message.
  const captureStartedRef = useRef(false);
  const [captureStarted, setCaptureStarted] = useState(false);

  // Remembers whether the component is still on screen, so a capture that
  // finishes after the user navigated away doesn't try to update state.
  const isMountedRef = useRef(true);
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  async function capturePhoto() {
    if (captureStartedRef.current) return;
    if (!cameraRef.current || !isCameraReady) return;
    captureStartedRef.current = true;
    setCaptureStarted(true);

    // Try twice: the first attempt occasionally fails right after the
    // session starts, and a second attempt a moment later nearly always
    // succeeds. `quality: 0.8` keeps the upload small while still being
    // clear enough to read text off a medicine label.
    for (let attempt = 1; attempt <= 2; attempt += 1) {
      try {
        const photo = await cameraRef.current.takePictureAsync({ quality: 0.8 });
        if (isMountedRef.current) onPhotoCaptured(photo.uri);
        return;
      } catch (error) {
        console.warn(`Camera capture failed (attempt ${attempt}):`, error);
        if (attempt < 2) await sleep(RETRY_DELAY_MS);
      }
    }

    // Both attempts failed: let the user tap the button again instead of
    // leaving the component stuck in "capture started".
    if (isMountedRef.current) {
      captureStartedRef.current = false;
      setCaptureStarted(false);
    }
  }

  // Reports the first barcode seen, once. Nothing is captured here - the
  // user still decides when to take the photo, and the backend reads the
  // barcode from that photo.
  const reportedBarcodeRef = useRef(false);
  function handleBarcodeScanned(result) {
    if (reportedBarcodeRef.current) return;
    reportedBarcodeRef.current = true;
    onBarcodeFound(result.data);
  }

  async function handleUploadFromGallery() {
    const result = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ["images"],
      quality: 0.8,
    });
    if (!result.canceled && result.assets && result.assets.length > 0) {
      onPhotoCaptured(result.assets[0].uri);
    }
  }

  // --- Permission not yet decided, or explicitly denied ---
  if (!permission) {
    // Permission status is still being checked - render nothing for this
    // brief moment rather than flashing an incorrect message.
    return null;
  }

  if (!permission.granted) {
    return (
      <View style={styles.centered}>
        <Text style={styles.permissionText}>
          {text.cameraPermissionMessage}
        </Text>
        <Pressable style={styles.primaryButton} onPress={requestPermission}>
          <Text style={styles.primaryButtonLabel}>
            {text.cameraPermissionButton}
          </Text>
        </Pressable>

        {/* Even without camera permission, uploading from the gallery
            should still work - same "always available fallback"
            principle as the web app. */}
        <Pressable onPress={handleUploadFromGallery} style={{ marginTop: 20 }}>
          <Text style={styles.linkText}>{text.uploadFromGalleryButton}</Text>
        </Pressable>
      </View>
    );
  }

  // --- Camera permission granted: show the live preview ---
  return (
    <View style={styles.container}>
      <CameraView
        ref={cameraRef}
        style={styles.camera}
        facing="back"
        onCameraReady={() => setIsCameraReady(true)}
        // Restricting to common retail/product barcode formats (rather
        // than every format the library supports) avoids false triggers
        // from unrelated codes and keeps scanning fast.
        barcodeScannerSettings={{
          barcodeTypes: ["ean13", "ean8", "upc_a", "code128", "qr"],
        }}
        // Always wired up (see the note at the top about not changing
        // camera props right before a capture); duplicate sightings are
        // ignored inside the handler instead.
        onBarcodeScanned={handleBarcodeScanned}
      />

      <Text style={styles.statusText}>
        {!isCameraReady
          ? text.cameraStarting
          : captureStarted
            ? text.scanningOcrVision
            : text.homeSubheading}
      </Text>

      <Pressable
        style={[styles.primaryButton, !isCameraReady && styles.primaryButtonDisabled]}
        onPress={capturePhoto}
        disabled={!isCameraReady}
      >
        <Text style={styles.primaryButtonLabel}>{text.takePhotoButton}</Text>
      </Pressable>

      <Pressable onPress={handleUploadFromGallery} style={{ marginTop: 16 }}>
        <Text style={styles.linkText}>{text.uploadFromGalleryButton}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    width: "100%",
    alignItems: "center",
  },
  camera: {
    width: "100%",
    aspectRatio: 3 / 4,
    borderRadius: theme.radiusLarge,
    overflow: "hidden",
  },
  statusText: {
    fontSize: theme.fontSize.label,
    marginTop: 12,
    color: theme.colors.text,
  },
  primaryButton: {
    width: "100%",
    minHeight: theme.touchTargetMin,
    backgroundColor: theme.colors.primary,
    borderRadius: theme.radiusLarge,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 16,
  },
  primaryButtonDisabled: {
    opacity: 0.5,
  },
  primaryButtonLabel: {
    color: theme.colors.textOnPrimary,
    fontSize: theme.fontSize.button,
    fontWeight: "700",
  },
  linkText: {
    fontSize: theme.fontSize.label,
    textDecorationLine: "underline",
    color: theme.colors.text,
  },
  centered: {
    width: "100%",
    alignItems: "center",
    padding: 20,
  },
  permissionText: {
    fontSize: theme.fontSize.body,
    color: theme.colors.text,
    textAlign: "center",
    marginBottom: 16,
  },
});
