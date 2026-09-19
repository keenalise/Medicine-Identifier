# ==============================================================================
# main.py
#
# WHAT THIS FILE DOES (in plain words):
# This is the "brain" of the app. The frontend sends it a photo of a
# medicine, and this file tries to figure out THREE things:
#   1. What medicine is it?          (name + what it's used for)
#   2. When does it expire?          (the expiry date printed on it)
#   3. How confident are we?         (so the frontend can ask the user to
#                                      confirm or correct the guess)
#
# It tries to answer question 1 in THREE STEPS, in order, stopping as soon
# as one step succeeds - this matches the plan we agreed on:
#
#   STEP 1 - BARCODE: Many medicine boxes have a barcode. If we can read
#            one, and we already know what that barcode means (from our own
#            small database), that's the fastest and most reliable answer.
#
#   STEP 2 - OCR (reading the printed text): If there's no barcode, or we
#            don't recognize it, we read whatever text IS printed on the
#            box/strip (in Nepali and/or English) and try to match it
#            against medicine names we know.
#
#   STEP 3 - VISION MODEL (fallback): If OCR text is unclear or matches
#            nothing we know (common with worn, creased, or unfamiliar
#            packaging), we ask an AI vision model to just LOOK at the
#            photo directly and describe what medicine it thinks this is.
#            This step needs internet + a free API key (see .env.example).
#
# Expiry-date reading is attempted throughout using a simple pattern-search
# (looking for words like "EXP" or "म्याद" near something that looks like a
# date), independent of which of the 3 steps above identified the medicine.
# ==============================================================================

import os
import re
import io
import json
from datetime import date

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import pytesseract
from pyzbar.pyzbar import decode as decode_barcodes
from dotenv import load_dotenv

# Loads the GEMINI_API_KEY (and any other secrets) from a local ".env" file,
# if one exists. See .env.example for what variable names are expected.
load_dotenv()

# ------------------------------------------------------------------------
# App setup
# ------------------------------------------------------------------------

app = FastAPI(title="Medicine Identifier Backend")

# CORS = "Cross-Origin Resource Sharing". In plain words: browsers block a
# webpage from one address (our frontend, e.g. http://localhost:3000) from
# talking to a server on a different address (our backend, e.g.
# http://localhost:8000) UNLESS the server explicitly says "it's okay, I
# allow requests from that address." This block is what says that.
#
# NOTE: "*" (allow everyone) is fine for local development, but before you
# put this online for real users, change this to your actual deployed
# frontend address only, for security.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------------
# Load our small local medicine database (see medicine_db.json).
# We read it ONCE, when the server starts, and keep it in memory - looking
# things up in memory is instant, unlike re-reading the file on every
# request.
# ------------------------------------------------------------------------

DB_PATH = os.path.join(os.path.dirname(__file__), "medicine_db.json")

with open(DB_PATH, "r", encoding="utf-8") as db_file:
    _raw_db = json.load(db_file)

MEDICINES_BY_ID = _raw_db["medicines"]
BARCODE_TO_ID = _raw_db["by_barcode"]
# The JSON file has some "_comment" keys used only to explain itself to
# humans reading it - they're not real barcodes, so we remove them here.
BARCODE_TO_ID.pop("_comment", None)

# ------------------------------------------------------------------------
# Set up the vision-model fallback (Step 3), only if an API key was
# provided. If it wasn't, the app still works - it just can't use Step 3,
# and will say so honestly instead of crashing.
# ------------------------------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
_vision_model = None

if GEMINI_API_KEY:
    import google.generativeai as genai

    genai.configure(api_key=GEMINI_API_KEY)
    # NOTE: Google renames/updates their free-tier model names occasionally.
    # "gemini-1.5-flash" is correct as of this writing, but if this line
    # errors out with a "model not found" message, check
    # https://ai.google.dev/gemini-api/docs/models for the current free
    # model name and update the string below.
    _vision_model = genai.GenerativeModel("gemini-1.5-flash")


# ------------------------------------------------------------------------
# STEP 2 helper: try to read an expiry date out of whatever text we have
# (whether that text came from OCR or from the vision model).
# ------------------------------------------------------------------------

# Words that typically appear right before/near an expiry date on
# packaging, in both English and Nepali. If we see one of these words, we
# know a date is probably nearby.
EXPIRY_KEYWORDS = [
    r"exp\.?",
    r"expiry",
    r"expiry date",
    r"best before",
    r"best after",
    r"use before",
    r"म्याद",
    r"म्याद सकिने",
]

# Common ways an expiry date is printed on packaging:
#   12/2026        (MM/YYYY)
#   12/26           (MM/YY)
#   12-2026
#   05/12/2026      (DD/MM/YYYY)
DATE_PATTERN = re.compile(
    r"(\d{1,2}[/\-]\d{4})|(\d{1,2}[/\-]\d{2})(?!\d)|(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})"
)


def find_expiry_text(raw_text: str) -> str | None:
    """
    Looks through `raw_text` for an expiry-related keyword, and if found,
    searches the nearby text for something that looks like a date.

    Returns the raw matched date text (e.g. "12/2026") if found, or None
    if nothing date-like was found near an expiry keyword.

    NOTE: This deliberately returns the RAW text, not a cleaned-up date,
    because the frontend should show the user exactly what was found
    (next to the confirm/correct buttons) rather than us silently
    "interpreting" it - reducing the chance of a wrong guess reaching the
    user unchecked.
    """
    lowered = raw_text.lower()

    for keyword in EXPIRY_KEYWORDS:
        keyword_match = re.search(keyword, lowered)
        if not keyword_match:
            continue

        # Look at a window of text starting right after the keyword (the
        # date is almost always printed right after words like "EXP"), up
        # to 20 characters ahead - enough room for a date, not so much that
        # we might grab an unrelated number from elsewhere on the label.
        window_start = keyword_match.end()
        window_text = raw_text[window_start : window_start + 20]

        date_match = DATE_PATTERN.search(window_text)
        if date_match:
            return date_match.group(0)

    return None


# ------------------------------------------------------------------------
# STEP 1: try to identify the medicine from a barcode in the photo.
# ------------------------------------------------------------------------

def try_barcode_lookup(image: Image.Image) -> dict | None:
    """
    Looks for a barcode in the image. If one is found AND we recognize it
    (it's in our medicine_db.json "by_barcode" table), returns the matching
    medicine's info. Otherwise returns None, so the caller knows to move on
    to Step 2 (OCR).
    """
    barcodes = decode_barcodes(image)
    if not barcodes:
        return None

    # A box might have more than one barcode printed on it (e.g. a
    # manufacturer code AND a retail barcode) - we just try each one until
    # one matches something we know.
    for barcode in barcodes:
        barcode_text = barcode.data.decode("utf-8", errors="ignore")
        medicine_id = BARCODE_TO_ID.get(barcode_text)
        if medicine_id and medicine_id in MEDICINES_BY_ID:
            return {
                "source": "barcode",
                "medicine_id": medicine_id,
                "raw_barcode": barcode_text,
            }

    # We found a barcode, but it's not in our database yet. Rather than
    # silently failing, we say so - this is useful information (it tells
    # you which barcodes to add to medicine_db.json over time).
    return {
        "source": "barcode_unknown",
        "medicine_id": None,
        "raw_barcode": barcodes[0].data.decode("utf-8", errors="ignore"),
    }


# ------------------------------------------------------------------------
# STEP 2: try to identify the medicine by reading the printed text (OCR).
# ------------------------------------------------------------------------

def try_ocr_lookup(image: Image.Image) -> dict:
    """
    Reads whatever text is visible in the image (in Nepali and/or English)
    and tries to match it against the brand/generic names in our database.

    Always returns a dict (never None) - even if nothing matched, the
    caller still needs the raw OCR text to search for an expiry date.
    """
    # "nep+eng" tells Tesseract to try recognizing BOTH Devanagari and
    # Latin script in the same pass, since packaging often mixes both
    # (e.g. an English brand name next to Nepali usage instructions).
    # NOTE: this requires the Nepali language pack to be installed on the
    # system - see the setup note at the bottom of this file if you get a
    # "nep.traineddata not found" style error.
    raw_text = pytesseract.image_to_string(image, lang="nep+eng")

    matched_medicine_id = None
    lowered_text = raw_text.lower()

    for medicine_id, info in MEDICINES_BY_ID.items():
        if medicine_id == "_comment":
            continue
        names_to_check = [info["generic_name"]] + info.get("brand_names", [])
        for name in names_to_check:
            if name.lower() in lowered_text:
                matched_medicine_id = medicine_id
                break
        if matched_medicine_id:
            break

    return {
        "source": "ocr" if matched_medicine_id else "ocr_unmatched",
        "medicine_id": matched_medicine_id,
        "raw_text": raw_text,
    }


# ------------------------------------------------------------------------
# STEP 3 (fallback): ask the vision model to look at the photo directly.
# ------------------------------------------------------------------------

def try_vision_fallback(image: Image.Image) -> dict:
    """
    Only called when barcode + OCR both failed to confidently identify the
    medicine. Sends the photo to a vision-capable AI model and asks it to
    describe the medicine, its purpose, and any expiry text it can see.

    Returns a dict describing what it found, or a dict with
    source="vision_unavailable" if no API key was configured, so the
    caller (and eventually the user) knows WHY no answer came back,
    instead of it looking like a silent failure.
    """
    if _vision_model is None:
        return {"source": "vision_unavailable", "medicine_name": None, "raw_text": ""}

    # We ask specifically for JSON output so our code can parse it
    # reliably, instead of trying to make sense of free-form paragraphs.
    prompt = (
        "You are looking at a photo of a medicine box or strip, possibly "
        "with Nepali and/or English text on it. "
        "Reply with ONLY a JSON object (no extra words, no markdown) in "
        "exactly this shape: "
        '{"medicine_name": "...", "purpose_ne": "...", "expiry_text": "..."}. '
        "purpose_ne must be written in Nepali, in one short simple sentence "
        "a non-medical person can understand. "
        "expiry_text should be the expiry date exactly as printed, or an "
        "empty string if you cannot find one. "
        "If you are not confident what the medicine is, set medicine_name "
        "to an empty string rather than guessing."
    )

    try:
        response = _vision_model.generate_content([prompt, image])
        # The model sometimes wraps JSON in ```json ... ``` even when asked
        # not to - this strips that off before parsing, just in case.
        cleaned = response.text.strip().strip("`").removeprefix("json").strip()
        parsed = json.loads(cleaned)
    except Exception:
        # Could be a network error, a rate-limit (free tier), or the model
        # replying in a format we couldn't parse. Either way, we fail
        # gracefully rather than crashing the whole request.
        return {"source": "vision_error", "medicine_name": None, "raw_text": ""}

    return {
        "source": "vision",
        "medicine_name": parsed.get("medicine_name") or None,
        "purpose_ne": parsed.get("purpose_ne") or None,
        "raw_text": parsed.get("expiry_text") or "",
    }


# ------------------------------------------------------------------------
# The main endpoint the frontend calls: POST /scan with an image file.
# ------------------------------------------------------------------------

@app.post("/scan")
async def scan_medicine(photo: UploadFile = File(...)):
    """
    Runs the full barcode -> OCR -> vision pipeline on one uploaded photo
    and returns a single, combined answer for the frontend to show.
    """
    # Read the uploaded file into memory and open it as an image we can
    # actually process (PIL = Python's standard image-handling library).
    try:
        image_bytes = await photo.read()
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read the uploaded image")

    medicine_id = None
    identification_source = None
    fallback_name = None  # used when the vision model names a medicine
    fallback_purpose_ne = None  # used when the vision model describes it
    ocr_text_for_expiry = ""  # whatever text we gather along the way

    # --- STEP 1: barcode ---
    barcode_result = try_barcode_lookup(image)
    if barcode_result and barcode_result["medicine_id"]:
        medicine_id = barcode_result["medicine_id"]
        identification_source = "barcode"

    # --- STEP 2: OCR (only if barcode didn't already give us an answer) ---
    if medicine_id is None:
        ocr_result = try_ocr_lookup(image)
        ocr_text_for_expiry = ocr_result["raw_text"]
        if ocr_result["medicine_id"]:
            medicine_id = ocr_result["medicine_id"]
            identification_source = "ocr"

    # --- STEP 3: vision model fallback (only if steps 1 and 2 both failed) ---
    if medicine_id is None:
        vision_result = try_vision_fallback(image)
        if vision_result["source"] == "vision":
            fallback_name = vision_result["medicine_name"]
            fallback_purpose_ne = vision_result.get("purpose_ne")
            identification_source = "vision"
            # The vision model might have found expiry text where OCR
            # didn't - fold it in so we still try to parse it below.
            ocr_text_for_expiry += "\n" + vision_result.get("raw_text", "")

    # --- Expiry date: attempt regardless of which step identified the medicine ---
    expiry_raw_text = find_expiry_text(ocr_text_for_expiry)

    # --- Build the final answer ---
    if medicine_id:
        info = MEDICINES_BY_ID[medicine_id]
        result = {
            "identified": True,
            "source": identification_source,
            "generic_name": info["generic_name"],
            "purpose_ne": info["use_ne"],
            "purpose_en": info["use_en"],
        }
    elif fallback_name:
        # We don't have this medicine in our own database, but the vision
        # model gave us its best guess directly.
        result = {
            "identified": True,
            "source": identification_source,
            "generic_name": fallback_name,
            "purpose_ne": fallback_purpose_ne,
            "purpose_en": None,  # vision model was only asked for Nepali
        }
    else:
        # Nothing worked. Being upfront about this (rather than returning
        # a guess) matters a lot given who this app is for.
        result = {
            "identified": False,
            "source": identification_source or "none",
            "generic_name": None,
            "purpose_ne": None,
            "purpose_en": None,
        }

    result["expiry_raw_text"] = expiry_raw_text  # e.g. "12/2026", or None
    # This tells the frontend: always show the big ✅/❌ confirm buttons,
    # never treat a guess (from ANY of the 3 steps) as final on its own.
    result["needs_user_confirmation"] = True

    return result


# ------------------------------------------------------------------------
# A tiny endpoint just to check the server is alive - useful for the
# frontend (or you, in a browser) to quickly confirm the backend is
# actually running, without needing to test the full photo-upload flow.
# ------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    return {"status": "ok"}


# ==============================================================================
# HOW TO RUN THIS (one-time setup):
#
# 1. System-level tools (these are NOT Python packages, install separately):
#      - Tesseract OCR, with the Nepali language pack:
#          Ubuntu/Debian: sudo apt install tesseract-ocr tesseract-ocr-nep
#      - zbar (needed by the pyzbar barcode library):
#          Ubuntu/Debian: sudo apt install libzbar0
#
# 2. Python packages:
#      pip install -r requirements.txt
#
# 3. Copy .env.example to .env and fill in GEMINI_API_KEY (optional - the
#    app still runs without it, it just can't do Step 3 / vision fallback).
#
# 4. Start the server:
#      uvicorn main:app --reload --port 8000
#
#    Then the frontend's TODO (backend step) comments in app/page.jsx
#    should call: http://localhost:8000/scan
# ==============================================================================