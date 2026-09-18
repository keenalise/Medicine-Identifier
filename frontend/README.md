# Medicine Identifier — Frontend (v1, camera + barcode only)

This is step 1 of the project: the frontend only. There is no backend yet —
capturing a barcode or photo just shows a placeholder screen so you can see
that the camera and barcode-scanning pieces actually work.

## What's built so far

- `app/layout.tsx` — loads the Baloo 2 font and wraps the app in the
  language system.
- `app/globals.css` — all colors and font sizes, defined once as variables.
- `lib/i18n.ts` — every piece of text in the app, in Nepali and English.
- `lib/LanguageContext.tsx` — remembers which language is active and lets
  any screen switch it.
- `components/LanguageToggle.tsx` — the "English / नेपाली" pill button.
- `components/CameraCapture.tsx` — opens the camera, scans for a barcode
  live, and can take a still photo or accept a gallery upload.
- `app/page.tsx` — the home screen that ties it all together.

## How to run it

You'll need [Node.js](https://nodejs.org) installed (v18 or newer).

```bash
cd frontend
npm install
npm run dev
```

Then open the printed URL (usually `http://localhost:3000`) — on a phone,
your browser will ask for camera permission the first time.

> Camera access requires either `localhost` or a proper `https://` address —
> plain `http://` on a real device will NOT be allowed to use the camera.
> When you deploy this later (e.g. to Vercel), it will automatically get
> `https://`, so this only matters for testing on a real phone during
> development (you may need a tool like `ngrok` for that).

## What's intentionally NOT built yet (next steps)

- No backend — barcode/photo capture currently just shows a placeholder.
  The exact spots where the backend call needs to go are marked with
  `// TODO (backend step)` comments in `app/page.tsx`.
- No OCR / vision-model identification (that lives in the backend).
- No expiry-date confirmation screen with the big ✅/❌ buttons (comes once
  the backend can actually return a guessed medicine + expiry date).
- No offline support, audio output, or Bikram Sambat calendar — all parked
  as future work per the project plan.
