// ============================================================================
// src/api.js
//
// WHAT THIS FILE DOES (in plain words):
// The one place the mobile app talks to the backend. It takes the photo the
// camera (or gallery) produced and uploads it to the backend's POST /scan
// endpoint - exactly what the web app does in app/page.jsx - and hands
// back the backend's answer (medicine name, purpose, expiry date...).
//
// Kept separate from the screens so that if the backend address or the
// request format ever changes, only this file needs editing.
//
// WHY expo-file-system's File IS USED:
// Expo (SDK 52+) replaces the global `fetch` with its own standards-based
// one, and that fetch only knows how to send `Blob`/`File` objects inside
// a FormData upload. The old React Native trick of appending a plain
// `{uri, name, type}` object fails with "Unsupported FormDataPart
// implementation". `File` from expo-file-system wraps the photo's file://
// path as a real Blob-compatible object (it has bytes(), name and type),
// which Expo's fetch streams correctly.
// ============================================================================

import { File } from "expo-file-system";
import { BACKEND_URL } from "./config";

// The backend can take a while on a hard photo: a few seconds of OCR plus,
// when it has to ask the vision model, up to ~30 s if the free tier is
// rate-limiting. Give up after this so the user is never stuck forever.
const REQUEST_TIMEOUT_MS = 60_000;

/**
 * Uploads the photo at `photoUri` (a file:// path from expo-camera or
 * expo-image-picker) to the backend and returns the parsed JSON result.
 * Throws on network failure, timeout, or a non-2xx reply.
 */
export async function scanPhoto(photoUri) {
  // The field name "photo" must match what the backend's /scan expects.
  // The filename and content type the backend sees come from the File
  // itself (the photo's own name, image/jpeg for camera photos); the
  // backend only cares about the image bytes anyway.
  const formData = new FormData();
  formData.append("photo", new File(photoUri));

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  try {
    const response = await fetch(`${BACKEND_URL}/scan`, {
      method: "POST",
      body: formData,
      // NOTE: do NOT set a Content-Type header here. fetch adds the correct
      // "multipart/form-data; boundary=..." itself; setting it by hand
      // drops the boundary and the backend can't parse the upload.
      signal: controller.signal,
    });

    if (!response.ok) {
      throw new Error(`Backend responded with status ${response.status}`);
    }
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}
