"use client";

// ============================================================================
// components/CameraCapture.jsx
//
// WHAT THIS FILE DOES (in plain words):
// This component turns on the phone/laptop camera and shows a live preview.
// While the camera is running, it constantly checks the video for a
// barcode (the striped pattern printed on many medicine boxes). This
// matches the plan: "try the barcode first, since it's the fastest and
// most reliable way to identify a medicine if one is printed."
//
// If a barcode IS found -> we immediately tell the parent screen via the
//   onBarcodeFound callback, and stop using the camera.
// If the user instead presses "Take Photo" (because no barcode was found,
//   or the box doesn't have one) -> we grab a single still image from the
//   video and hand it to the parent via onPhotoCaptured, so it can be sent
//   for OCR / vision-based identification instead.
//
// There is also a plain file-upload fallback, for:
//   - Desktop testing/development where a webcam may behave differently.
//   - Users who prefer picking an existing photo from their gallery.
//
// Props this component expects:
//   onBarcodeFound(barcodeText)  - called the moment a barcode is read
//   onPhotoCaptured(photoBlob)   - called when a still photo is taken/uploaded
// ============================================================================

import { useEffect, useRef, useState } from "react";
import { BrowserMultiFormatReader } from "@zxing/browser";
import { useLanguage } from "../lib/LanguageContext";

export default function CameraCapture({ onBarcodeFound, onPhotoCaptured }) {
  const { text } = useLanguage();

  // A "ref" here is just a stable handle to the actual <video> and
  // <canvas> HTML elements on the page, so we can control them directly
  // (start the camera, grab a frame) the way plain JavaScript would.
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const barcodeFoundRef = useRef(false);

  // Tracks whether we are still actively looking for a barcode, so we can
  // show the "Looking for a barcode..." message and stop it later.
  const [isScanningBarcode, setIsScanningBarcode] = useState(true);
  const [cameraError, setCameraError] = useState(null);

  useEffect(() => {
    // This object from the ZXing library does the actual barcode-reading
    // work: it watches a <video> element frame by frame and tries to
    // decode any barcode it can see.
    const barcodeReader = new BrowserMultiFormatReader();
    let isCancelled = false;
    let scannerControls = null;

    async function startCameraAndScan() {
      try {
        // "environment" asks for the REAR camera on a phone, since that's
        // the one used to photograph objects (the front camera is for
        // selfies/video calls).
        scannerControls = await barcodeReader.decodeFromConstraints(
          { video: { facingMode: "environment" } },
          videoRef.current,
          (result, error) => {
            // This callback fires repeatedly, many times per second, as
            // the library keeps scanning new video frames.
            if (isCancelled) return;

            if (result) {
              // A barcode was successfully read! Stop scanning and hand
              // the result up to the parent screen.
              barcodeFoundRef.current = true;
              setIsScanningBarcode(false);
              onBarcodeFound(result.getText());
              handleTakePhoto(); // also capture a frame so it can be sent to the backend
            }
            // Note: `error` fires constantly too (it just means "no
            // barcode visible in THIS particular frame"), so we
            // deliberately do nothing with it - that's normal, not a
            // real problem.
          }
        );
      } catch (err) {
        // This happens if the browser/device refuses camera access, e.g.
        // the user denied the permission prompt.
        setCameraError(text.errorGeneric);
      }
    }

    startCameraAndScan();

    // Cleanup: when this component is no longer shown (user navigated
    // away), make sure we release the camera. Leaving a camera running in
    // the background would drain battery and is a privacy concern.
    return () => {
      isCancelled = true;
      scannerControls?.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  // If no barcode is found within a few seconds, don't leave the user
  // stuck on "looking for a barcode" forever - automatically move on to
  // taking a photo instead, same as if they'd pressed the button
  // themselves. Many medicines simply don't have a scannable barcode.
  useEffect(() => {
    const timer = setTimeout(() => {
      if (!barcodeFoundRef.current) {
        setIsScanningBarcode(false);
        handleTakePhoto();
      }
    }, 5000);

    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  // Called when the user presses the big "Take Photo" button - used when
  // no barcode was found, or the medicine doesn't have one.
  function handleTakePhoto() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    // Draw the CURRENT video frame onto the (invisible) canvas, matching
    // the video's real resolution so we don't lose image quality.
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext("2d");
    context?.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Convert that canvas drawing into an actual image file (a Blob) we
    // can later send to the backend, the same way a photo file works.
    canvas.toBlob((blob) => {
      if (blob) onPhotoCaptured(blob);
    }, "image/jpeg");
  }

  // Called when the user picks an existing photo from their gallery
  // instead of using the live camera.
  function handleFileUpload(event) {
    const file = event.target.files?.[0];
    if (file) onPhotoCaptured(file);
  }

    return (
    <div style={{ width: "100%", textAlign: "center" }}>
      {cameraError && (
        <p style={{ color: "var(--color-danger)", marginBottom: "16px" }}>
          {cameraError}
        </p>
      )}

      {!cameraError && (
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
            }}
          />
          <p style={{ fontSize: "var(--font-size-label)", marginTop: "12px" }}>
            {isScanningBarcode ? text.scanningBarcode : text.scanningOcrVision}
          </p>

          <button
            onClick={handleTakePhoto}
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
            }}
          >
            {text.takePhotoButton}
          </button>
        </>
      )}

      {/* Hidden canvas - always present so handleTakePhoto can use it
          whenever the camera IS working. */}
      <canvas ref={canvasRef} style={{ display: "none" }} />

      {/* Upload-from-gallery is always available, even if the camera
          failed to start (denied permission, no webcam, etc.) - it's
          the fallback path, not just a convenience. */}
      <label
        style={{
          display: "block",
          marginTop: "16px",
          fontSize: "var(--font-size-label)",
          textDecoration: "underline",
          color: "var(--color-text)",
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
