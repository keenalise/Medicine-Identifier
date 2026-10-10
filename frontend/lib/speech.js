// ============================================================================
// lib/speech.js
//
// WHAT THIS FILE DOES (in plain words):
// Reads a sentence out loud - the medicine's name, what it's for and the
// expiry date - in Nepali or English, for people who can't easily read
// the screen.
//
// HOW: it first asks the backend's /speak endpoint for an MP3 of the
// sentence (made with Google Translate's free speech service, which speaks
// Nepali well). If the backend can't be reached, it falls back to the
// browser's own built-in voices (the Web Speech API) - those are free and
// offline but almost never include Nepali, so for Nepali text the closest
// available voice (Hindi reads Devanagari acceptably) is used instead.
// ============================================================================

let currentAudio = null;

function stopEverything() {
  if (currentAudio) {
    currentAudio.pause();
    currentAudio = null;
  }
  if (typeof window !== "undefined" && window.speechSynthesis) {
    window.speechSynthesis.cancel();
  }
}

// Plays the backend's MP3. Resolves when playback ends; rejects when the
// backend is unreachable or the browser refuses to play.
function playFromBackend(backendUrl, text, lang) {
  return new Promise((resolve, reject) => {
    const url = `${backendUrl}/speak?lang=${encodeURIComponent(lang)}&text=${encodeURIComponent(text)}`;
    const audio = new Audio(url);
    currentAudio = audio;
    audio.onended = () => resolve();
    audio.onerror = () => reject(new Error("backend speech unavailable"));
    audio.play().catch(reject);
  });
}

// Browser voices: pick the best match for the language, if any.
function pickVoice(lang) {
  const voices = window.speechSynthesis.getVoices();
  const wanted = lang === "ne" ? ["ne", "hi"] : ["en"];
  for (const prefix of wanted) {
    const voice = voices.find((v) => v.lang.toLowerCase().startsWith(prefix));
    if (voice) return voice;
  }
  return null;
}

function speakWithBrowser(text, lang) {
  return new Promise((resolve, reject) => {
    if (typeof window === "undefined" || !window.speechSynthesis) {
      reject(new Error("no speech support"));
      return;
    }
    const utterance = new SpeechSynthesisUtterance(text);
    const voice = pickVoice(lang);
    if (voice) utterance.voice = voice;
    utterance.lang = lang === "ne" ? "ne-NP" : "en-US";
    utterance.rate = 0.9; // a touch slower than default - easier to follow
    utterance.onend = () => resolve();
    utterance.onerror = (event) => reject(new Error(event.error || "speech failed"));
    window.speechSynthesis.speak(utterance);
  });
}

/**
 * Speaks `text` in `lang` ("ne" or "en"). Stops anything already playing
 * first. Never throws - a failure just means silence, and the caller can
 * show a message if it wants to.
 */
export async function speak(backendUrl, text, lang) {
  if (!text) return false;
  stopEverything();
  try {
    await playFromBackend(backendUrl, text, lang);
    return true;
  } catch (error) {
    console.warn("Backend speech failed, trying the browser's voices:", error);
  }
  try {
    await speakWithBrowser(text, lang);
    return true;
  } catch (error) {
    console.warn("Browser speech failed:", error);
    return false;
  }
}

export function stopSpeaking() {
  stopEverything();
}
