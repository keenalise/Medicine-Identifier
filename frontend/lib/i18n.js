// ============================================================================
// lib/i18n.js
//
// WHAT THIS FILE DOES (in plain words):
// This is the "phrase book" for the whole app. Every piece of text a user
// sees - button labels, headings, messages - lives here in TWO languages:
// Nepali ("ne") and English ("en").
//
// Why keep all the text in one place instead of writing it directly inside
// each screen? Because the app has an "English" toggle button that must
// switch EVERY piece of text on the page at once. If the text were scattered
// across many files, the toggle button would have no easy way to find and
// swap it all. By keeping every phrase here, the toggle button just has to
// say "use the 'ne' column" or "use the 'en' column", and every screen
// automatically shows the right language.
// ============================================================================

// The Nepali phrase book. This is the DEFAULT language the app opens in,
// because most of the intended users are more comfortable reading Nepali
// than English.
const ne = {
  appName: "औषधि चिनुहोस्",
  toggleButtonLabel: "English",

  homeHeading: "औषधिको फोटो खिच्नुहोस्",
  homeSubheading: "औषधिको बट्टा वा पत्ता क्यामेरा अगाडि राख्नुहोस्",
  takePhotoButton: "फोटो खिच्नुहोस्",
  uploadFromGalleryButton: "ग्यालरीबाट छान्नुहोस्",

  scanningBarcode: "बारकोड खोजिँदैछ...",
  scanningOcrVision: "औषधि पहिचान गरिँदैछ...",
  scanningFailedRetry: "पत्ता लगाउन सकिएन, फेरि प्रयास गर्नुहोस्",

  resultPurposeLabel: "यो औषधि यसको लागि हो:",
  resultExpiryLabel: "म्याद सकिने मिति:",
  resultExpiredWarning: "⚠️ यो औषधिको म्याद सकिसक्यो, प्रयोग नगर्नुहोस्",
  confirmCorrectButton: "✅ ठीक छ",
  confirmWrongButton: "❌ मिलेन",

  correctionPromptExpiry: "सही मिति छान्नुहोस्",
  correctionPromptName: "सही औषधिको नाम छान्नुहोस्",
  correctionSaveButton: "सुरक्षित गर्नुहोस्",

  errorNoInternet: "इन्टरनेट जडान छैन",
  errorGeneric: "समस्या भयो, फेरि प्रयास गर्नुहोस्",
  tryAgainButton: "फेरि प्रयास गर्नुहोस्",
};

// The English phrase book. Shown only after the user taps the toggle.
const en = {
  appName: "Identify Medicine",
  toggleButtonLabel: "नेपाली",

  homeHeading: "Take a photo of the medicine",
  homeSubheading: "Hold the medicine box or strip in front of the camera",
  takePhotoButton: "Take Photo",
  uploadFromGalleryButton: "Choose from Gallery",

  scanningBarcode: "Looking for a barcode...",
  scanningOcrVision: "Identifying the medicine...",
  scanningFailedRetry: "Could not identify it, please try again",

  resultPurposeLabel: "This medicine is for:",
  resultExpiryLabel: "Expiry date:",
  resultExpiredWarning: "⚠️ This medicine has expired, do not use it",
  confirmCorrectButton: "✅ Correct",
  confirmWrongButton: "❌ Not right",

  correctionPromptExpiry: "Please pick the correct expiry date",
  correctionPromptName: "Please pick the correct medicine",
  correctionSaveButton: "Save",

  errorNoInternet: "No internet connection",
  errorGeneric: "Something went wrong, please try again",
  tryAgainButton: "Try Again",
};

// A simple lookup table: give it "ne" or "en", get back the matching
// phrase book.
export const dictionaries = { ne, en };
