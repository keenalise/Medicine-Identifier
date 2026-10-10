# औषधि चिनुहोस् · Medicine Identifier

Point a phone camera at a medicine box or strip and get back, in Nepali or
English: **what the medicine is**, **what it is for**, and **when it
expires**. Built for people in rural Nepal who may not read English and
cannot easily check small print themselves. Text is large, the layout is
high contrast, and every answer is shown with big ✅ / ❌ buttons so the
user confirms it rather than trusting a machine guess.

## What is in this repository

```
medicine-identifier/
  backend/    FastAPI server that does the actual identification
  frontend/   Next.js web app (works in a phone browser)
  mobile/     Expo / React Native app (Expo Go during development)
  *.jpeg      A real strip photo used as a test fixture (see "Testing")
```

The three parts are independent projects with their own dependencies.
The web app and the mobile app look and behave the same, and both talk to
the same backend.

## How identification works

The backend tries three steps in order and stops as soon as one works:

1. **Barcode** - decoded with `pyzbar` and looked up in `medicine_db.json`.
2. **OCR** - Tesseract reads the printed text (Nepali + English) and the
   result is matched against brand and generic names in `medicine_db.json`.
3. **Vision model** - the photo is sent to Google Gemini, which names the
   medicine and describes its purpose in Nepali. Needs internet and a key.

The **expiry date** is read separately from whichever step identified the
medicine (`backend/expiry_parser.py`):

- Text next to an expiry label ("EXP", "Expiry", "म्याद") is trusted.
- Text next to a manufacturing label ("MFG", "Mfd", "निर्माण मिति") is
  never shown as the expiry.
- OCR often misreads foil strips ("MFG" as "MEG", "0" as "O", the year
  chopped off). The parser tolerates those, rejects implausible dates, and
  if several unlabeled dates are present picks the latest one.
- When OCR cannot produce a complete, labelled date, the backend asks the
  vision model for just the expiry date. A half-read or manufacturing date
  is withheld rather than shown.

The response always carries `needs_user_confirmation: true`.

## Requirements

| Part | Needs |
|---|---|
| backend | Python 3.12, Tesseract 5 with the `nep` language pack, `libzbar0`, a Gemini API key (optional but strongly recommended) |
| frontend | Node 18 or newer |
| mobile | Node **20.19.4 or newer** (Expo SDK 57 refuses to start on Node 18), the **Expo Go** app on your phone |

On Ubuntu/Debian the system packages are:

```bash
sudo apt install tesseract-ocr tesseract-ocr-nep libzbar0
```

## Running the backend

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
cp env.example .env        # then put your key in GEMINI_API_KEY=
./venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

`--host 0.0.0.0` lets phones on the same Wi-Fi reach the server (needed by
the mobile app); drop it if only the web app on this machine will use it.

Get a free key at <https://aistudio.google.com/apikey>. Without a key the
server still runs, but step 3 is off and expiry dates will only appear when
OCR reads them cleanly, which is rare on foil strips.

On startup the server prints whether the vision model is `ENABLED`. Check
it any time at <http://localhost:8000/health>:

```json
{"status": "ok", "vision_enabled": true,
 "vision_models": {"gemini-3.6-flash": "resting until 05:48",
                   "gemini-3.1-flash-lite": "available", "gemini-flash-lite-latest": "available"}}
```

**The free Gemini tier is small: about 20 requests per model per day**
(plus a per-minute limit), and the counter resets at midnight Pacific
time. A scan uses one request, or two when the medicine was not matched
by OCR. The backend therefore never spends a request at startup, tries the
models listed in `VISION_MODEL_NAMES` (`backend/vision_fallback.py`) in
order, and when one reports its daily quota used up it rests that model
and moves to the next. `/health` shows a resting model as
`"resting until HH:MM"`. If every model is resting, scans still work but
the expiry comes from OCR alone, which on foil strips usually means none.
Each scan also prints one `[scan]` line to the console saying what OCR
found, what the vision model did, and how long each took.

Google retires model names regularly. If scans log `NotFound`, update
`VISION_MODEL_NAMES` from <https://ai.google.dev/gemini-api/docs/models>.

### API

`POST /scan` with a multipart form field named `photo` (JPEG or PNG).

```bash
curl -F "photo=@6e8bf737-6bf5-4944-8e5b-695cae283121.jpeg" http://localhost:8000/scan
```

```json
{
  "identified": true,
  "source": "ocr",
  "generic_name": "Paracetamol",
  "generic_name_ne": "प्यारासिटामोल",
  "purpose_ne": "टाउको दुखाइ र ज्वरोको लागि प्रयोग गरिन्छ",
  "purpose_en": "Used for fever and mild pain (headache, body ache)",
  "expiry_raw_text": "20 JUN.2029",
  "expiry_text_ne": "२० जुन २०२९",
  "needs_user_confirmation": true
}
```

`source` is one of `barcode`, `ocr`, `vision`, or `none`. `expiry_raw_text`
is the date exactly as printed; `expiry_text_ne` is the same date with
Devanagari digits and Nepali month names for display. Both are `null` when
no trustworthy expiry date was found.

### Adding medicines

`backend/medicine_db.json` holds a small starter list (paracetamol, ORS,
omeprazole, cetirizine, amoxicillin). Add an entry under `medicines` with
`generic_name`, `generic_name_ne`, `brand_names`, `use_ne`, `use_en`, and
map scanned barcodes to ids under `by_barcode`. The server reads the file
once at startup, so restart it after editing.

## Running the web app

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>. The backend address is set at the top of
`frontend/app/page.jsx` (`BACKEND_URL`, default `http://localhost:8000`).

To use it from a phone on the same Wi-Fi, replace `localhost` in
`BACKEND_URL` with your computer's LAN address (for example
`http://192.168.1.71:8000`) and open `http://<that address>:3000` on the
phone. Browsers only allow the camera on `https` or `localhost`, so on a
plain `http://192.168...` address the "choose from gallery" button is the
way to supply a photo.

## Running the mobile app

The mobile app shows the camera, and when the user taps **"Take Photo"**
(or picks one from the gallery) it uploads the photo to the backend's
`/scan` and shows the medicine's name, purpose, and expiry date with
✅ / ❌ buttons, the same as the web app. Nothing is captured
automatically; the user decides when the medicine is in focus. Full
details, troubleshooting included, are in `mobile/README.md`.

The phone cannot reach `localhost` on your laptop, so two things matter:

1. Start the backend listening on the Wi-Fi interface, not just localhost:

   ```bash
   cd backend
   ./venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

2. The app works out the laptop's address by itself from the Expo dev
   server (see `mobile/src/config.js`). If that guess is wrong, for example
   when using `--tunnel`, set `BACKEND_URL_OVERRIDE` in that file to
   something like `http://192.168.1.71:8000`. The error screen shows which
   address was tried.

To run it:

```bash
# Expo needs Node 20+. If you use nvm:
nvm use 22

cd mobile
npm install
npx expo start
```

Install **Expo Go** from the Play Store / App Store, make sure the phone is
on the same Wi-Fi as the computer, and scan the QR code that `expo start`
prints. If the phone cannot connect, run `npx expo start --tunnel` and set
`BACKEND_URL_OVERRIDE` as described above.

## Testing

The backend has regression tests for the expiry parser, built from text
Tesseract actually produced on real strips:

```bash
cd backend
./venv/bin/python test_expiry_parser.py     # or: pytest test_expiry_parser.py
```

The JPEG in the repository root is a real NIKO paracetamol strip whose
date line reads `MFG.21 JUN.2026 EXP.20 JUN.2029`, printed sideways on
textured foil. It is a good end-to-end check: with the vision model
enabled the backend returns `20 JUN.2029`; with it disabled it returns no
expiry at all, which is the intended safe behaviour (it must never return
the manufacturing date).

## Project status

- [x] Web app: camera, barcode scanning, Nepali/English UI, backend call
- [x] Backend: barcode, OCR, vision fallback, expiry parsing
- [x] Mobile app: camera, barcode scanning, backend call, result screen
- [ ] Mobile app: production build with EAS (currently runs in Expo Go)
- [ ] Save user confirmations / corrections to grow `medicine_db.json`
- [ ] Lock down CORS (`allow_origins=["*"]` in `backend/main.py`) and
      pick a real backend address before deploying for other people
