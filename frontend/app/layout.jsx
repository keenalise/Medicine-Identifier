// ============================================================================
// app/layout.jsx
//
// WHAT THIS FILE DOES (in plain words):
// Next.js wraps EVERY page of the app inside this file automatically. It's
// the right place to do things that should apply everywhere, such as:
//   - Loading the "Baloo 2" font (works for both Nepali/Devanagari and
//     English/Latin text, and looks big and friendly rather than a generic
//     app font).
//   - Making sure the page is sized correctly on phone screens.
//   - Turning on the language system (see lib/LanguageContext.jsx) so every
//     screen inside the app can show Nepali or English text.
// ============================================================================

import { LanguageProvider } from "../lib/LanguageContext";
import "./globals.css";

export const metadata = {
  title: "औषधि चिनुहोस् | Identify Medicine",
  description:
    "Take a photo of a medicine to learn what it is for and its expiry date, in Nepali.",
};

// This stops phones from letting users accidentally "pinch zoom" the whole
// app layout out of shape, while keeping normal accessibility zoom.
export const viewport = {
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }) {
  return (
    <html lang="ne">
      <head>
        {/* Baloo 2 supports both Devanagari (Nepali) and Latin (English)
            scripts natively, so the same friendly, rounded typeface works
            for both languages without switching fonts on toggle. */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;600;700;800&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        {/* Everything inside LanguageProvider can now use the
            useLanguage() hook to read/switch between Nepali and English. */}
        <LanguageProvider>{children}</LanguageProvider>
      </body>
    </html>
  );
}
