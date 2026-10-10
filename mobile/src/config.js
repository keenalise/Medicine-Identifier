// ============================================================================
// src/config.js
//
// WHAT THIS FILE DOES (in plain words):
// Decides WHERE the backend server is, i.e. the address the phone should
// send photos to.
//
// On a phone, "localhost" means the phone itself - NOT your laptop - so the
// web app's "http://localhost:8000" would never work here. During
// development the phone and the laptop are on the same Wi-Fi, and the Expo
// dev server (the thing `npx expo start` runs) already knows the laptop's
// Wi-Fi address, because that's how the phone downloaded the app. We reuse
// that address and just swap the port for the backend's (8000).
//
// So in the normal case there's nothing to configure. If that ever guesses
// wrong (e.g. you started Expo with --tunnel, or the backend runs on
// another machine), set BACKEND_URL_OVERRIDE below and it wins.
//
// REMINDER: the backend must be started so it listens on the Wi-Fi
// interface, not only on localhost:
//     uvicorn main:app --reload --host 0.0.0.0 --port 8000
// ============================================================================

import Constants from "expo-constants";

// Leave empty to auto-detect. Example: "http://192.168.1.71:8000"
const BACKEND_URL_OVERRIDE = "";

const BACKEND_PORT = 8000;

function detectDevServerHost() {
  // e.g. "192.168.1.71:8081" while running through `npx expo start`.
  const hostUri =
    Constants.expoConfig?.hostUri ||
    Constants.manifest2?.extra?.expoClient?.hostUri ||
    "";
  const host = hostUri.split(":")[0];
  // A tunnel address (something.exp.direct) is NOT the laptop's Wi-Fi
  // address, so it cannot reach the backend - treat it as "unknown".
  if (!host || host.includes("exp.direct")) return null;
  return host;
}

const detectedHost = detectDevServerHost();

export const BACKEND_URL =
  BACKEND_URL_OVERRIDE ||
  (detectedHost ? `http://${detectedHost}:${BACKEND_PORT}` : `http://localhost:${BACKEND_PORT}`);

// True when we had to fall back to localhost, which will not work on a real
// phone - the UI uses this to show a helpful hint instead of a vague error.
export const BACKEND_URL_IS_GUESS = !BACKEND_URL_OVERRIDE && !detectedHost;
