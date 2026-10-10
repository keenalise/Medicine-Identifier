// ============================================================================
// src/speech.js
//
// WHAT THIS FILE DOES (in plain words):
// Reads a sentence out loud - the medicine's name, what it's for and the
// expiry date - in Nepali or English, for people who can't easily read
// the screen. Mobile twin of the web app's lib/speech.js.
//
// HOW: it first asks the backend's /speak endpoint for an MP3 of the
// sentence (made with Google Translate's free speech service, which speaks
// Nepali well) and plays it with expo-audio. If the backend can't be
// reached, it falls back to the phone's own speech engine (expo-speech) -
// free and offline, but most phones have no Nepali voice, so for Nepali
// text the closest available voice (Hindi reads Devanagari acceptably) is
// used instead.
// ============================================================================

import { createAudioPlayer, setAudioModeAsync } from "expo-audio";
import * as Speech from "expo-speech";
import { BACKEND_URL } from "./config";

let currentPlayer = null;
let audioModeReady = false;

async function ensureAudioMode() {
  if (audioModeReady) return;
  try {
    // Play even when the phone's ringer switch is on silent - the user
    // pressed "listen" on purpose, so they expect to hear something.
    await setAudioModeAsync({ playsInSilentMode: true });
  } catch (error) {
    console.warn("Could not set audio mode:", error);
  }
  audioModeReady = true;
}

function stopEverything() {
  if (currentPlayer) {
    try {
      currentPlayer.pause();
      currentPlayer.remove();
    } catch (_error) {
      // already released - nothing to do
    }
    currentPlayer = null;
  }
  Speech.stop();
}

// Plays the backend's MP3. Resolves when playback ends; rejects when the
// backend is unreachable, the file can't be decoded, or nothing starts
// playing within a few seconds.
function playFromBackend(text, lang) {
  return new Promise((resolve, reject) => {
    const url = `${BACKEND_URL}/speak?lang=${encodeURIComponent(lang)}&text=${encodeURIComponent(text)}`;
    const player = createAudioPlayer({ uri: url });
    currentPlayer = player;
    let finished = false;
    const finish = (error) => {
      if (finished) return;
      finished = true;
      clearTimeout(startTimer);
      subscription.remove();
      if (currentPlayer === player) {
        try {
          player.remove();
        } catch (_e) {
          // ignore
        }
        currentPlayer = null;
      }
      error ? reject(error) : resolve();
    };
    const subscription = player.addListener("playbackStatusUpdate", (status) => {
      if (status.didJustFinish) finish();
      // expo-audio reports a failed load through the status too
      if (status.playbackState === "error") finish(new Error("audio failed to load"));
    });
    // If nothing has started after a while (backend down, bad address),
    // give up so the fallback voice can take over.
    const startTimer = setTimeout(() => {
      if (!player.playing && !finished) finish(new Error("audio did not start"));
    }, 8000);
    try {
      player.play();
    } catch (error) {
      finish(error);
    }
  });
}

// Phone voices: pick the best match for the language, if any.
async function pickVoice(lang) {
  try {
    const voices = await Speech.getAvailableVoicesAsync();
    const wanted = lang === "ne" ? ["ne", "hi"] : ["en"];
    for (const prefix of wanted) {
      const voice = voices.find((v) => (v.language || "").toLowerCase().startsWith(prefix));
      if (voice) return voice;
    }
  } catch (_error) {
    // voice listing not supported - let the engine choose
  }
  return null;
}

async function speakWithPhone(text, lang) {
  const voice = await pickVoice(lang);
  return new Promise((resolve, reject) => {
    Speech.speak(text, {
      language: voice?.language || (lang === "ne" ? "ne-NP" : "en-US"),
      voice: voice?.identifier,
      rate: 0.9, // a touch slower than default - easier to follow
      onDone: () => resolve(),
      onStopped: () => resolve(),
      onError: (error) => reject(error || new Error("speech failed")),
    });
  });
}

/**
 * Speaks `text` in `lang` ("ne" or "en"). Stops anything already playing
 * first. Resolves to true when something was heard, false otherwise -
 * never throws, so the caller just shows a small message on false.
 */
export async function speak(text, lang) {
  if (!text) return false;
  stopEverything();
  await ensureAudioMode();
  try {
    await playFromBackend(text, lang);
    return true;
  } catch (error) {
    console.warn("Backend speech failed, trying the phone's voices:", error);
  }
  try {
    await speakWithPhone(text, lang);
    return true;
  } catch (error) {
    console.warn("Phone speech failed:", error);
    return false;
  }
}

export function stopSpeaking() {
  stopEverything();
}
