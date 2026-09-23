"use client";

// ============================================================================
// components/CameraCapture.jsx
//
// WHAT THIS FILE DOES (in plain words):
// Turns on the phone/laptop camera, shows a live preview, and watches the
// video for a barcode. If a barcode is found, or the user presses "Take
// Photo" (or a few seconds pass with no barcode), a still photo is grabbed
// and handed to the parent screen so it can be sent to the backend.
//
// There is also a plain "choose from gallery" upload, which keeps working
// even when the camera cannot start.
//
// Props:
//   onBarcodeFound(barcodeText)  - called the moment a barcode is read
//   onPhotoCaptured(photoBlob)   - called when a still photo is taken/uploaded
//
// WHAT CHANGED vs. THE PREVIOUS VERSION (why the camera wouldn't start):
//   1. React dev mode (Strict Mode) starts and stops every effect twice.
//      The old code started the camera twice on the SAME <video> element,
//      and the first start could never be stopped, leaving a black screen.
//      Now the start is delayed by one tick so only the real one runs, and
//      a camera that finishes starting after we were closed is stopped.
//   2. The old 5-second auto-photo timer began at page load, even while the
//      browser was still asking for camera permission (video size 0), so
//      the photo was empty/failed. The timer now begins only once the
//      camera is really running.
//   3. After a barcode was read, the old code kept firing on every video
//      frame, sending many photos. Now it fires once.
//   4. Errors are now specific (permission denied / no camera / camera in
//      use / not a secure connection) and are shown in the current
//      language, instead of one generic message that never changed language.
// ============================================================================

import { useEffect, useRef, useState } from "react";
import { BrowserMultiFormatReader } from "@zxing/browser";
import { useLanguage } from "../lib/LanguageContext";

// If no barcode is found this many milliseconds after the camera starts,
// a photo is taken automatically. Set to 0 to turn auto-photo off and
// only take a photo when the user presses the button.
const AUTO_PHOTO_DELAY_MS = 5000;

// Which phrase (in lib/i18n.js) to show for each kind of camera problem.
const ERROR_TEXT_KEYS = {
  insecure: "cameraErrorInsecure",
  denied: "cameraErrorDenied",
  notFound: "cameraErrorNotFound",
  inUse: "cameraErrorInUse",
  generic: "errorGeneric",
};

// Turns the browser's technical error into one of the kinds above.
function errorKindFor(err) {
  const name = err?.name;
  if (name === "NotAllowedError" || name === "SecurityError") return "denied";
  if (name === "NotFoundError" || name === "DevicesNotFoundError") return "notFound";
  if (name === "NotReadableError" || name === "TrackStartError") return "inUse";
  return "generic";
}

export default function CameraCapture({ onBarcodeFound, onPhotoCaptured }) {
  const { text } = useLanguage();

  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const barcodeFoundRef = useRef(false);
  const photoSentRef = useRef(false);

  // Always hold the LATEST callbacks, so the long-running camera code
  // below never calls an out-of-date copy of them.
  const onBarcodeFoundRef = useRef(onBarcodeFound);
  const onPhotoCapturedRef = useRef(onPhotoCaptured);
  onBarcodeFoundRef.current = onBarcodeFound;
  onPhotoCapturedRef.current = onPhotoCaptured;

  const [isScanningBarcode, setIsScanningBarcode] = useState(true);
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraErrorKind, setCameraErrorKind] = useState(null);

  // --- Start the camera + barcode scanning ---------------------------------
  useEffect(() => {
    let isCancelled = false;
    let scannerControls = null;

    async function startCameraAndScan() {
      // Browsers only allow camera access on https:// or http://localhost.
      // Opening the app by a network address (e.g. http://192.168.1.5:3000)
      // makes navigator.mediaDevices undefined.
      if (!navigator.mediaDevices?.getUserMedia) {
        setCameraErrorKind(window.isSecureContext ? "generic" : "insecure");
        return;
      }

      const barcodeReader = new BrowserMultiFormatReader();
      try {
        const controls = await barcodeReader.decodeFromConstraints(
          // "ideal" rear camera: uses the back camera on a phone, but
          // still works on a laptop that only has one webcam.
          { video: { facingMode: { ideal: "environment" } }, audio: false },
          videoRef.current,
          (result) => {
            // Fires many times per second. "No barcode in this frame" is
            // normal and ignored; only act on the first real result.
            if (isCancelled || !result || barcodeFoundRef.current) return;

            barcodeFoundRef.current = true;
            setIsScanningBarcode(false);
            onBarcodeFoundRef.current(result.getText());
            takePhoto(); // also send a still frame to the backend
          }
        );

        if (isCancelled) {
          // We were closed while the camera was still starting: release it.
          controls.stop();
          return;
        }
        scannerControls = controls;
        setCameraReady(true);
      } catch (err) {
        if (isCancelled) return;
        console.error("Camera failed to start:", err);
        setCameraErrorKind(errorKindFor(err));
      }
    }

    // Wait one tick before starting. In React dev mode this effect is run,
    // immediately cleaned up, and run again - clearing the timer means only
    // the second (real) run actually opens the camera.
    const startTimer = setTimeout(startCameraAndScan, 0);

    return () => {
      isCancelled = true;
      clearTimeout(startTimer);
      scannerControls?.stop(); // release the camera when leaving the screen
    };
  }, []);

  // --- Auto-photo if no barcode is found -----------------------------------
  useEffect(() => {
    if (!cameraReady || !AUTO_PHOTO_DELAY_MS) return;

    const timer = setTimeout(() => {
      if (!barcodeFoundRef.current) {
        setIsScanningBarcode(false);
        takePhoto();
      }
    }, AUTO_PHOTO_DELAY_MS);

    return () => clearTimeout(timer);
  }, [cameraReady]);

  // --- Grab one still photo from the live video ----------------------------
  function takePhoto() {
    if (photoSentRef.current) return; // never send two photos

    const video = videoRef.current;
    const canvas = canvasRef.current;
    // videoWidth is 0 until the camera is really delivering frames.
    if (!video || !canvas || !video.videoWidth) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);

    photoSentRef.current = true;
    canvas.toBlob(
      (blob) => {
        if (blob) {
          onPhotoCapturedRef.current(blob);
        } else {
          photoSentRef.current = false; // failed - allow another try
        }
      },
      "image/jpeg",
      0.92
    );
  }

  // Photo picked from the gallery instead of the live camera.
  function handleFileUpload(event) {
    const file = event.target.files?.[0];
    if (file) onPhotoCapturedRef.current(file);
  }

  return (
    <div style={{ width: "100%", textAlign: "center" }}>
      {cameraErrorKind && (
        <p style={{ color: "var(--color-danger)", marginBottom: "16px" }}>
          {text[ERROR_TEXT_KEYS[cameraErrorKind]]}
        </p>
      )}

      {!cameraErrorKind && (
        <>
          {/* Live camera preview */}
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            style={{
              width: "100%",
              maxWidth: "480px",
              borderRadius: "var(--radius-large)",
              background: "#000",
              minHeight: "240px",
            }}
          />
          <p style={{ fontSize: "var(--font-size-label)", marginTop: "12px" }}>
            {!cameraReady
              ? text.cameraStarting
              : isScanningBarcode
                ? text.scanningBarcode
                : text.scanningOcrVision}
          </p>

          <button
            onClick={takePhoto}
            disabled={!cameraReady}
            style={{
              width: "100%",
              maxWidth: "480px",
              minHeight: "var(--touch-target-min)",
              fontSize: "var(--font-size-button)",
              fontWeight: 700,
              color: "var(--color-text-on-primary)",
              background: "var(--color-primary)",
              border: "none",
              borderRadius: "var(--radius-large)",
              marginTop: "16px",
              opacity: cameraReady ? 1 : 0.5,
            }}
          >
            {text.takePhotoButton}
          </button>
        </>
      )}

      {/* Hidden canvas used to grab the still photo. */}
      <canvas ref={canvasRef} style={{ display: "none" }} />

      {/* Upload-from-gallery is always available, even if the camera
          failed to start - it's the fallback path. */}
      <label
        style={{
          display: "block",
          marginTop: "16px",
          fontSize: "var(--font-size-label)",
          textDecoration: "underline",
          color: "var(--color-text)",
          cursor: "pointer",
        }}
      >
        {text.uploadFromGalleryButton}
        <input
          type="file"
          accept="image/*"
          onChange={handleFileUpload}
          style={{ display: "none" }}
        />
      </label>
    </div>
  );
}