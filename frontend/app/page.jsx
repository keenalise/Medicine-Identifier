"use client";

// ============================================================================
// app/page.jsx
//
// WHAT THIS FILE DOES (in plain words):
// This is the home screen. It shows:
//   1. A bright header with the app name and the language toggle button.
//   2. The camera screen (default).
//   3. A "loading" screen while the photo is being sent to the backend
//      and identified.
//   4. A result screen showing what the backend found - medicine name,
//      what it's for, and the expiry date - with big ✅/❌ buttons so the
//      user confirms it themselves rather than trusting a guess blindly.
//
// This is where the frontend finally talks to the backend's /scan
// endpoint - the TODO comments from earlier versions of this file are now
// filled in.
// ============================================================================

import { useState } from "react";
import CameraCapture from "../components/CameraCapture";
import LanguageToggle from "../components/LanguageToggle";
import { useLanguage } from "../lib/LanguageContext";

// The backend's address during local development. Later, when this app is
// deployed somewhere real, this should come from an environment variable
// instead of being hardcoded - but for testing on your own machine, this
// is correct as-is.
const BACKEND_URL = "http://localhost:8000";

// What screen we're showing, and any data that screen needs:
//   { type: "none" }                       - camera screen
//   { type: "loading" }                    - waiting for the backend
//   { type: "result", photoUrl, data }      - backend responded
//   { type: "error" }                       - something went wrong

export default function HomePage() {
  const { text, language } = useLanguage();
  const [capture, setCapture] = useState({ type: "none" });

  // Called when a barcode is detected live by the camera. The actual
  // identification now happens via the photo sent in handlePhotoCaptured
  // (CameraCapture.jsx also grabs a still photo the moment a barcode is
  // found), so this just needs to exist - it doesn't need to do anything
  // itself.
  function handleBarcodeFound(_barcodeText) {
    // Intentionally empty - see comment above.
  }

  async function handlePhotoCaptured(photo) {
    setCapture({ type: "loading" });
    const photoUrl = URL.createObjectURL(photo);

    // Package the photo as a file upload, matching what the backend's
    // /scan endpoint expects (a form field named "photo").
    const formData = new FormData();
    formData.append("photo", photo, "medicine.jpg");

    try {
      const response = await fetch(`${BACKEND_URL}/scan`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Backend responded with status ${response.status}`);
      }

      const data = await response.json();
      setCapture({ type: "result", photoUrl, data });
    } catch (error) {
      // Common causes: the backend isn't running, or there's no internet
      // connection (needed for the vision-model fallback step). Either
      // way, we tell the user plainly rather than leaving them staring
      // at a spinner forever.
      console.error("Scan request failed:", error);
      setCapture({ type: "error" });
    }
  }

  function handleReset() {
    setCapture({ type: "none" });
  }

  function handleConfirmation(wasCorrect) {
    // TODO (future step): send this confirmation/correction back to the
    // backend so it can be logged and used to grow medicine_db.json and
    // eventually train the image-classification model, as planned.
    console.log("User confirmed result was correct:", wasCorrect);
    handleReset();
  }

  return (
    <main style={{ minHeight: "100vh", background: "var(--color-surface)" }}>
      <header
        style={{
          background:
            "linear-gradient(135deg, var(--color-hero-start), var(--color-hero-end))",
          padding: "20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <h1
          style={{
            color: "var(--color-text-on-primary)",
            fontSize: "var(--font-size-heading)",
            margin: 0,
          }}
        >
          {text.appName}
        </h1>
        <LanguageToggle />
      </header>

      <section style={{ padding: "24px 20px", textAlign: "center" }}>
        {capture.type === "none" && (
          <>
            <h2 style={{ fontSize: "var(--font-size-heading)" }}>
              {text.homeHeading}
            </h2>
            <p
              style={{
                fontSize: "var(--font-size-label)",
                marginBottom: "24px",
              }}
            >
              {text.homeSubheading}
            </p>
            <CameraCapture
              onBarcodeFound={handleBarcodeFound}
              onPhotoCaptured={handlePhotoCaptured}
            />
          </>
        )}

        {capture.type === "loading" && (
          <p style={{ fontSize: "var(--font-size-body)" }}>
            {text.scanningOcrVision}
          </p>
        )}

        {capture.type === "error" && (
          <div>
            <p style={{ fontSize: "var(--font-size-body)", color: "var(--color-danger)" }}>
              {text.errorGeneric}
            </p>
            <ResetButton onClick={handleReset} label={text.tryAgainButton} />
          </div>
        )}

        {capture.type === "result" && (
          <ResultScreen
            photoUrl={capture.photoUrl}
            data={capture.data}
            text={text}
            language={language}
            onConfirm={() => handleConfirmation(true)}
            onReject={() => handleConfirmation(false)}
          />
        )}
      </section>
    </main>
  );
}

// The screen shown after the backend responds: the photo, what it found,
// and the big confirm/reject buttons - never presenting a guess as final
// on its own.
function ResultScreen({ photoUrl, data, text, language, onConfirm, onReject }) {
  // Show the medicine name in the current language when the backend
  // provided one: Nepali name in Nepali mode, English name in English mode
  // (falling back to whichever is available).
  const nameText =
    language === "en" ? data.generic_name : data.generic_name_ne || data.generic_name;
  // The backend only fills in purpose_en when a local database entry was
  // matched (not when the vision-model fallback answered) - fall back to
  // the Nepali text either way rather than showing a blank in English mode.
  const purposeText =
    language === "en" && data.purpose_en ? data.purpose_en : data.purpose_ne;

  return (
    <div>
      <img
        src={photoUrl}
        alt="Captured medicine"
        style={{
          width: "100%",
          maxWidth: "480px",
          borderRadius: "var(--radius-large)",
        }}
      />

      {data.identified ? (
        <div style={{ marginTop: "20px" }}>
          <p style={{ fontSize: "var(--font-size-heading)", fontWeight: 700 }}>
            {nameText}
          </p>

          {purposeText && (
            <p style={{ fontSize: "var(--font-size-body)", marginTop: "8px" }}>
              {text.resultPurposeLabel} {purposeText}
            </p>
          )}

          <p style={{ fontSize: "var(--font-size-body)", marginTop: "8px" }}>
            {text.resultExpiryLabel}{" "}
            {data.expiry_text_ne || data.expiry_raw_text || "?"}
          </p>

          <div
            style={{
              display: "flex",
              gap: "16px",
              justifyContent: "center",
              marginTop: "24px",
            }}
          >
            <button
              onClick={onConfirm}
              style={{
                minHeight: "var(--touch-target-min)",
                padding: "0 28px",
                fontSize: "var(--font-size-button)",
                fontWeight: 700,
                color: "var(--color-text-on-primary)",
                background: "var(--color-success)",
                border: "none",
                borderRadius: "var(--radius-large)",
              }}
            >
              {text.confirmCorrectButton}
            </button>
            <button
              onClick={onReject}
              style={{
                minHeight: "var(--touch-target-min)",
                padding: "0 28px",
                fontSize: "var(--font-size-button)",
                fontWeight: 700,
                color: "var(--color-text-on-primary)",
                background: "var(--color-danger)",
                border: "none",
                borderRadius: "var(--radius-large)",
              }}
            >
              {text.confirmWrongButton}
            </button>
          </div>
        </div>
      ) : (
        <div style={{ marginTop: "20px" }}>
          <p style={{ fontSize: "var(--font-size-body)" }}>
            {text.scanningFailedRetry}
          </p>
          <ResetButton onClick={onReject} label={text.tryAgainButton} />
        </div>
      )}
    </div>
  );
}

function ResetButton({ onClick, label }) {
  return (
    <button
      onClick={onClick}
      style={{
        marginTop: "20px",
        minHeight: "var(--touch-target-min)",
        padding: "0 32px",
        fontSize: "var(--font-size-button)",
        fontWeight: 700,
        color: "var(--color-primary)",
        background: "var(--color-surface)",
        border: "3px solid var(--color-primary)",
        borderRadius: "var(--radius-large)",
      }}
    >
      {label}
    </button>
  );
}