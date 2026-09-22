// ============================================================================
// src/components/CameraCapture.js
//
// WHAT THIS FILE DOES (in plain words):
// The mobile equivalent of the web app's CameraCapture.jsx. Same behavior:
//   - Shows a live camera preview.
//   - Continuously watches for a barcode while the camera is open. If one
//     is found, calls onBarcodeFound immediately.
//   - Has a "Take Photo" button for when there's no barcode (or none was
//     found), which calls onPhotoCaptured with the captured photo.
//   - Has a "Choose from Gallery" fallback, always available, even if the
//     camera itself fails to start.
//
// KEY DIFFERENCE FROM THE WEB VERSION: on a phone, the OS itself needs to
// ask the user for camera permission (there's no browser doing that for
// us), so this file also has to handle "permission not yet granted" as
// its own screen state.
// ============================================================================

import { useRef, useState } from "react";
import { View, Text, Pressable, StyleSheet } from "react-native";
import { CameraView, useCameraPermissions } from "expo-camera";
import * as ImagePicker from "expo-image-picker";
import { useLanguage } from "../LanguageContext";
import { theme } from "../theme";

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

  // Once a barcode is found, we stop reacting to further scans (otherwise
  // onBarcodeFound could fire repeatedly per second while the camera
  // keeps looking at the same barcode).
  const [hasScannedBarcode, setHasScannedBarcode] = useState(false);

  function handleBarcodeScanned(result) {
    if (hasScannedBarcode) return; // already handled one, ignore further scans
    setHasScannedBarcode(true);
    onBarcodeFound(result.data);
  }

  async function handleTakePhoto() {
    if (!cameraRef.current) return;
    // Takes a still photo from the current camera view. `quality: 0.8`
    // keeps the file size reasonable for uploading over mobile data,
    // while still being clear enough to read text off a medicine label.
    const photo = await cameraRef.current.takePictureAsync({ quality: 0.8 });
    onPhotoCaptured(photo.uri);
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
        // Restricting to common retail/product barcode formats (rather
        // than every format the library supports) avoids false triggers
        // from unrelated codes and keeps scanning fast.
        barcodeScannerSettings={{
          barcodeTypes: ["ean13", "ean8", "upc_a", "code128", "qr"],
        }}
        onBarcodeScanned={hasScannedBarcode ? undefined : handleBarcodeScanned}
      />

      <Text style={styles.statusText}>
        {hasScannedBarcode ? text.scanningOcrVision : text.scanningBarcode}
      </Text>

      <Pressable style={styles.primaryButton} onPress={handleTakePhoto}>
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
