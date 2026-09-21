# Medicine Identifier

A web app to help people (especially elderly, non-English-speaking users in
rural Nepal) identify a medicine and its expiry date just by photographing
it - like Google Lens, but for medicine boxes and strips.

The UI is in Nepali by default, with a one-tap toggle to English. Text is
large and the layout is high-contrast, designed for older users.

## Project structure

```
medicine-identifier/
  frontend/    Next.js web app - camera, barcode scan, Nepali/English UI
  backend/     FastAPI server - identifies the medicine (barcode -> OCR ->
               AI vision fallback) and finds its expiry date
```

Each folder has its own more detailed README (`frontend/README.md`,
`backend/README.md`) - this file is the "start here" overview covering how
to run BOTH together.

## Current status

The frontend and backend both work on their own, but are **not yet wired
together** - capturing a photo currently just shows it back to you as a
placeholder, instead of actually sending it to the backend for
identification. That connection is the next planned step.

## How to run the whole project

You need **two terminal windows open at the same time** - one for the
backend, one for the frontend. Closing either terminal stops that half of
the app.

### Terminal 1 - Backend

```bash
cd backend

# One-time setup (skip if already done):
sudo apt install tesseract-ocr tesseract-ocr-nep libzbar0
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# open .env and add your Gemini API key (optional - see backend/README.md)

# Every time you want to run it:
source venv/bin/activate
uvicorn main:app --reload --port 8000
```

Confirm it's running by opening `http://localhost:8000/health` in a
browser - it should show `{"status":"ok"}`.

### Terminal 2 - Frontend

```bash
cd frontend

# One-time setup (skip if already done):
npm install

# Every time you want to run it:
npm run dev
```

Then open `http://localhost:3000` in a browser (or on your phone, once
deployed) - that's the actual app.

### Stopping everything

In each terminal, press `Ctrl+C` to stop that server.

## Full setup details

- Backend setup, troubleshooting, and how `/scan` works internally:
  see `backend/README.md`.
- Frontend setup and what's built so far: see `frontend/README.md`.

## What's built so far

**Frontend:**
- Camera capture with live barcode scanning
- Photo capture / gallery upload fallback
- Nepali-first UI with an English toggle button
- Large fonts, bright/high-contrast design for elderly users

**Backend:**
- `/scan` endpoint: barcode lookup -> OCR (Nepali + English) -> AI vision
  model fallback, in that order
- Expiry-date text detection, independent of which step IDs the medicine
- A small, growable local medicine database

## What's next / future work

- Connect the frontend's photo capture to the backend's `/scan` endpoint
  (currently a placeholder screen)
- Build the result/confirmation screen: cropped image + big ✅/❌ buttons
  so users confirm or correct the guess, rather than trusting it blindly
- Grow `medicine_db.json` with more real medicines and barcodes
- Train a custom image-classification model from confirmed/corrected scans
- Offline support, audio (Nepali text-to-speech) output, Bikram Sambat
  calendar support for expiry dates