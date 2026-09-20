# Medicine Identifier — Backend

This is the "brain" of the app: it takes a photo of a medicine (sent by the
frontend) and tries to identify what it is and when it expires, using three
steps in order — barcode, then OCR, then an AI vision model as a fallback.

## Project structure

```
backend/
  main.py             The FastAPI app - the "conductor". Wires the steps
                       together and exposes the /scan and /health endpoints.
  ocr.py               STEP 2: reads printed text off the packaging and
                       matches it against known medicines.
  vision_fallback.py   STEP 3: asks an AI vision model to look at the photo
                       directly, when barcode + OCR both fail.
  expiry_parser.py     Finds expiry-date text near keywords like "EXP" or
                       "म्याद", independent of which step IDs the medicine.
  medicine_db.json     Small local database: medicine names, Nepali/English
                       descriptions, and known barcodes. Meant to grow.
  requirements.txt     Python package dependencies.
  .env.example          Shows which environment variable names the app
                       expects (currently just GEMINI_API_KEY). Copy this
                       to ".env" and fill in real values there.
```

## How the /scan endpoint works

1. **Barcode** — look for a barcode in the photo. If found and it's in
   `medicine_db.json`, that's the answer.
2. **OCR** — if no barcode (or an unrecognized one), read the printed text
   (Nepali + English) and try to match it against known medicine names.
3. **Vision model fallback** — if OCR didn't confidently match anything,
   send the photo itself to a vision-capable AI model and ask it to
   identify the medicine directly. Needs internet + a free Gemini API key.
4. **Expiry date** — searched for throughout, regardless of which step
   above identified the medicine.

Every response includes `"needs_user_confirmation": true` — the app is
designed so a guess from ANY step is always shown to the user for a
✅/❌ confirmation, never treated as final on its own. See
`expiry_raw_text` in the response too — it's returned as raw text exactly
as found, not silently auto-converted, for the same reason.

## Setup

### 1. System-level tools (not Python packages — install separately)

```bash
sudo apt install tesseract-ocr tesseract-ocr-nep libzbar0
```

- `tesseract-ocr` + `tesseract-ocr-nep` — the actual OCR engine, plus the
  Nepali (Devanagari) language pack it needs to read Nepali text.
- `libzbar0` — required by the `pyzbar` barcode-reading library.

### 2. Python packages

It's a good idea to use a virtual environment so these packages don't mix
with other Python projects on your machine:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Environment variables

```bash
cp .env.example .env
```

Then open `.env` and fill in a real `GEMINI_API_KEY` (get one free at
https://aistudio.google.com/app/apikey — check that page for current
free-tier limits, since they can change). This step is optional — the
app still runs and answers via barcode/OCR without it, it just can't use
the Step 3 vision fallback.

### 4. Run the server

```bash
uvicorn main:app --reload --port 8000
```

`--reload` makes it restart automatically whenever you save a code
change, which is convenient while developing. Once running, you can check
it's alive by opening `http://localhost:8000/health` in a browser — it
should show `{"status": "ok"}`.

The frontend's `TODO (backend step)` comments (in `app/page.jsx`) are
where it should call `http://localhost:8000/scan`.

## Growing `medicine_db.json`

It ships with only 5 sample medicines. To add more:
- Add an entry under `"medicines"` with an id, brand names, generic name,
  and Nepali/English descriptions.
- If you know the medicine's barcode, add it under `"by_barcode"`,
  mapping the barcode number to that medicine's id.

## What's intentionally NOT built yet (future work)

- Training a custom image-classification model on common packaging
  (once enough confirmed/corrected scans have been collected).
- Offline support (everything currently requires internet for Step 3, and
  Tesseract itself needs to be installed locally either way).
- Audio (Nepali text-to-speech) output.
- Bikram Sambat calendar support for expiry dates.
- Logging user corrections (✅/❌ confirmations) to build a growing,
  verified dataset over time.