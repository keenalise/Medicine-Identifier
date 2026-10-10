# Medicine Identifier — Mobile (React Native / Expo)

The mobile version of the app, built with Expo. Same design, same Nepali/
English text, same camera + barcode-scanning behavior as the web version -
just packaged as a real installable app instead of a website.

This is a **separate project from `frontend/`** (the Next.js web app) -
they don't share code, but they're built to look and behave identically,
and both talk to the same `backend/`.

## How it works

1. The camera opens. A barcode, if one is in view, is noted quietly.
2. The user taps **"Take Photo"** (or picks a photo from the gallery).
   Nothing is captured automatically - the user decides when the medicine
   is lined up and in focus.
3. The photo is uploaded to the backend's `POST /scan`.
4. The backend answers with the medicine's name, what it is for, and the
   expiry date (see the root `README.md` for how it works that out).
5. The app shows the result with big ✅ / ❌ buttons so the user confirms
   it rather than trusting a machine guess.
6. A "🔊 सुन्नुहोस् / Listen" button reads the result out loud in the
   current language (see `src/speech.js`): the backend's `/speak` audio
   first (free Google Translate voices, which include Nepali), the phone's
   own voices (`expo-speech`) if the backend can't be reached.

## Why Expo (not "plain" React Native)

Expo lets you test on a real phone in minutes, without installing Android
Studio or Xcode first - you just scan a QR code with the **Expo Go** app.
That's the fastest path to actually seeing this running on your phone from
Ubuntu. Full custom native builds (for publishing to the Play Store) are a
later step, covered at the bottom of this file.

## Project structure

```
mobile/
  App.js               Entry point - loads fonts, sets up language system
  app.json              Expo config: app name, icon, camera/gallery
                        permission text
  src/
    config.js           Where the backend is (auto-detected, see below)
    api.js              The one function that uploads a photo to /scan
    speech.js           "Listen" button logic: backend audio, phone voices
    i18n.js             Same phrase book as the web app (Nepali/English)
    LanguageContext.js   Same language-switching logic as the web app
    theme.js             Colors/font sizes (React Native has no CSS
                        variables, so this is a plain JS object instead)
    components/
      LanguageToggle.js
      CameraCapture.js   Camera preview, take-photo button, gallery upload
    screens/
      HomeScreen.js      Camera -> "identifying..." -> result / error
```

## Setup on Ubuntu

### 0. Use Node 20 or newer

Expo SDK 57 refuses to start on Node 18 (`configs.toReversed is not a
function` is the symptom). With nvm:

```bash
nvm use 22
```

### 1. Install dependencies

From inside the `mobile` folder:

```bash
cd mobile
npm install
```

### 1b. Start the backend so the phone can reach it

The phone cannot reach `localhost` on your laptop, so the backend must
listen on the Wi-Fi interface:

```bash
cd ../backend
./venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The app finds the laptop's address on its own (`src/config.js` reads it
from the Expo dev server and swaps the port for 8000). If you use
`--tunnel`, or the backend runs elsewhere, set `BACKEND_URL_OVERRIDE` in
`src/config.js`, e.g. `"http://192.168.1.71:8000"`. The error screen
always shows which address was tried.

### 2. Install the Expo Go app on your phone

Search "Expo Go" on the Play Store (Android) or App Store (iPhone) and
install it. This is a free app from Expo that can run this project
without you needing to build/install a custom app package yet.

### 3. Start the dev server

```bash
npx expo start
```

This prints a QR code in your terminal.

### 4. Open it on your phone

**Your phone and your Ubuntu machine must be on the same Wi-Fi network.**
Open the Expo Go app and scan the QR code from your terminal (Android:
scan it from inside the Expo Go app; iPhone: scan it with the regular
Camera app, which will offer to open it in Expo Go).

The app should load on your phone within a few seconds, and will
automatically reload whenever you save a code change on your laptop -
no need to restart anything while developing.

### If your phone can't connect (common on some networks/routers)

Some Wi-Fi networks (especially ones with "client isolation" - common on
public or office Wi-Fi) block phone and laptop from seeing each other
directly. If the QR code / "same network" method doesn't work:

```bash
npx expo start --tunnel
```

This routes the connection through the internet instead of your local
network - slower, but works around that restriction. It'll ask to install
an additional package the first time (`@expo/ngrok`) - allow it.

## Camera & gallery permissions

The first time you tap the camera button, your phone will show its normal
"Allow [app] to access the camera?" popup - this is the OS itself asking,
not something this app controls. The permission text it shows comes from
`app.json`. If you deny it, the app still lets you use "Choose from
Gallery" instead, same fallback principle as the web version.

## What's built so far

Identical feature set to the web frontend:
- Live camera preview with quiet barcode detection
- Take-photo (on button tap only) and choose-from-gallery capture
- Upload to the backend's `/scan` and a result screen with the medicine
  name, purpose, expiry date and ✅ / ❌ confirmation buttons
- A "Listen" button that reads the result aloud in Nepali or English
- Nepali-first UI with an English toggle button
- Same bright, high-contrast, large-text design (Baloo 2 font, matching
  colors) as the web app

**Not built yet:** sending the ✅ / ❌ answer back to the backend (it is
only logged to the console for now).

## Troubleshooting

- **"समस्या भयो" / "Something went wrong" with an address under it** -
  the phone could not reach the backend at that address. Check the backend
  was started with `--host 0.0.0.0`, that phone and laptop share a Wi-Fi,
  and that the address is your laptop's (fix it with
  `BACKEND_URL_OVERRIDE` if not).
- **"Failed to capture image"** - the camera session was not ready. The
  take-photo button is disabled until the camera reports ready and a
  failed capture is retried once; if it still happens, use "Choose from
  Gallery".
- **"Unsupported FormDataPart implementation"** - Expo's `fetch` only
  accepts `Blob`/`File` objects in uploads, not the old React Native
  `{uri, name, type}` shape. `src/api.js` wraps the photo in
  `expo-file-system`'s `File` for this reason; keep it that way.

## Building a real, installable app (later step)

When you're ready to install this on your own phone permanently (not just
through Expo Go), or publish it, you'll use **EAS Build**
(`npx eas build`), Expo's cloud build service - this builds an actual
`.apk`/`.aab` (Android) or `.ipa` (iOS) file. That's a separate, later
step from everyday development, and needs a free Expo account. Ask when
you're ready to get there and we'll walk through it.
