"use client";

// ============================================================================
// app/page.jsx
//
// WHAT THIS FILE DOES (in plain words):
// This is the very first screen the user sees. It shows:
//   1. A bright header with the app name and the language toggle button.
//   2. Either the camera screen (default), or a simple "here's what we
//      captured" screen after a photo is taken / a barcode is found.
//
// NOTE FOR NEXT STEP: The backend (which actually identifies the medicine
// from the barcode/photo) doesn't exist yet - we're building the frontend
// first, as agreed. So for now, capturing a barcode or photo just moves to
// a placeholder "captured!" screen. The spots where the backend call will
// go are clearly marked with TODO comments below.
// ============================================================================

import { useState } from "react";
import CameraCapture from "../components/CameraCapture";
import LanguageToggle from "../components/LanguageToggle";
import { useLanguage } from "../lib/LanguageContext";

export default function HomePage() {
  const { text } = useLanguage();
  // `capture` tracks what we have captured so far, before the backend has
  // processed it: { type: "none" } | { type: "barcode", value } |
  // { type: "photo", photoUrl }
  const [capture, setCapture] = useState({ type: "none" });

  function handleBarcodeFound(barcodeText) {
    // TODO (backend step): send `barcodeText` to the /scan backend
    // endpoint to look up the medicine by barcode. For now we just record
    // it so the screen can show something happened.
    setCapture({ type: "barcode", value: barcodeText });
  }

  function handlePhotoCaptured(photo) {
    // TODO (backend step): send `photo` (as a file) to the /scan backend
    // endpoint, which will run OCR and, if needed, the vision-model
    // fallback. For now we just show the captured photo back to the user
    // so they can see the capture worked.
    const photoUrl = URL.createObjectURL(photo);
    setCapture({ type: "photo", photoUrl });
  }

  function handleReset() {
    setCapture({ type: "none" });
  }

  return (
    <main style={{ minHeight: "100vh", background: "var(--color-surface)" }}>
      {/* Bright hero header - the "bright colored background" the project
          asked for, contained to the header so body text stays easy to
          read against a plain surface underneath. */}
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

        {capture.type === "barcode" && (
          <div>
            <p style={{ fontSize: "var(--font-size-body)" }}>
              {/* Placeholder until the backend lookup exists */}
              Barcode captured: {capture.value}
            </p>
            <ResetButton onClick={handleReset} label={text.tryAgainButton} />
          </div>
        )}

        {capture.type === "photo" && (
          <div>
            <img
              src={capture.photoUrl}
              alt="Captured medicine"
              style={{
                width: "100%",
                maxWidth: "480px",
                borderRadius: "var(--radius-large)",
              }}
            />
            <ResetButton onClick={handleReset} label={text.tryAgainButton} />
          </div>
        )}
      </section>
    </main>
  );
}

// A small reusable "try again" button, shown on the placeholder result
// screens above. Kept as its own tiny component since it's used in two
// places with identical styling.
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
