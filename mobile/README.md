# Medicine Identifier — Mobile (React Native / Expo)

The mobile version of the app, built with Expo. Same design, same Nepali/
English text, same camera + barcode-scanning behavior as the web version -
just packaged as a real installable app instead of a website.

This is a **separate project from `frontend/`** (the Next.js web app) -
they don't share code, but they're built to look and behave identically,
and will eventually talk to the same `backend/`.

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
    i18n.js             Same phrase book as the web app (Nepali/English)
    LanguageContext.js   Same language-switching logic as the web app
    theme.js             Colors/font sizes (React Native has no CSS
                        variables, so this is a plain JS object instead)
    components/
      LanguageToggle.js
      CameraCapture.js   Camera + live barcode scanning + gallery upload
    screens/
      HomeScreen.js
```

## Setup on Ubuntu

### 1. Install dependencies

From inside the `mobile` folder:

```bash
cd mobile
npm install
```

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

Identical feature set to the web frontend at this stage:
- Live camera preview with barcode scanning
- Take-photo and choose-from-gallery capture
- Nepali-first UI with an English toggle button
- Same bright, high-contrast, large-text design (Baloo 2 font, matching
  colors) as the web app

**Not wired up yet:** capturing a photo/barcode just shows a placeholder
screen, same as the web app - the actual call to the backend's `/scan`
endpoint is a future step, marked with `// TODO (backend step)` comments
in `src/screens/HomeScreen.js`.

## Building a real, installable app (later step)

When you're ready to install this on your own phone permanently (not just
through Expo Go), or publish it, you'll use **EAS Build**
(`npx eas build`), Expo's cloud build service - this builds an actual
`.apk`/`.aab` (Android) or `.ipa` (iOS) file. That's a separate, later
step from everyday development, and needs a free Expo account. Ask when
you're ready to get there and we'll walk through it.
