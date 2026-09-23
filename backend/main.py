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
# as one step succeeds:
#
#   STEP 1 - BARCODE (handled right here in main.py): Many medicine boxes
#            have a barcode. If we can read one, and we already know what
#            that barcode means (from our own small database), that's the
#            fastest and most reliable answer.
#
#   STEP 2 - OCR, i.e. reading the printed text (see ocr.py): If there's no
#            barcode, or we don't recognize it, we read whatever text IS
#            printed on the box/strip and try to match it against medicine
#            names we know.
#
#   STEP 3 - VISION MODEL fallback (see vision_fallback.py): If OCR text is
#            unclear or matches nothing we know, we ask an AI vision model
#            to just LOOK at the photo directly and describe what medicine
#            it thinks this is. Needs internet + a free API key.
#
# Expiry-date reading (see expiry_parser.py) is attempted throughout using
# a simple pattern-search, independent of which of the 3 steps above
# identified the medicine.
#
# NOTE ON FILE STRUCTURE: Steps 2 and 3, and expiry-date parsing, each live
# in their OWN file (ocr.py, vision_fallback.py, expiry_parser.py). This
# file (main.py) is the "conductor" - it decides the ORDER things happen
# in and combines the results, but the detailed "how" for each step lives
# in that step's own file. Step 1 (barcode) is simple enough that it still
# lives directly in this file.
# ==============================================================================

import os
import io
import json

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from pyzbar.pyzbar import decode as decode_barcodes
from dotenv import load_dotenv

from ocr import try_ocr_lookup
from vision_fallback import create_vision_model, try_vision_fallback
from expiry_parser import find_expiry_text

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
# humans reading it - they're not real barcodes/medicines, so we remove
# them here.
BARCODE_TO_ID.pop("_comment", None)

# ------------------------------------------------------------------------
# Set up the vision-model fallback (Step 3), only if an API key was
# provided. If it wasn't, the app still works - it just can't use Step 3,
# and will say so honestly instead of crashing. This setup runs ONCE here
# at server startup - see vision_fallback.py for why that matters.
# ------------------------------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
_vision_model = create_vision_model(GEMINI_API_KEY)


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
    vision_expiry = ""

    # --- STEP 1: barcode ---
    barcode_result = try_barcode_lookup(image)
    if barcode_result and barcode_result["medicine_id"]:
        medicine_id = barcode_result["medicine_id"]
        identification_source = "barcode"

    # --- STEP 2: OCR (always run, so we can read the expiry date) ---
    ocr_result = try_ocr_lookup(image, MEDICINES_BY_ID)
    ocr_text_for_expiry = ocr_result["raw_text"]
    if medicine_id is None and ocr_result["medicine_id"]:
        medicine_id = ocr_result["medicine_id"]
        identification_source = "ocr"

    # --- STEP 3: vision model fallback (only if steps 1 and 2 both failed) ---
    if medicine_id is None:
        vision_result = try_vision_fallback(image, _vision_model)
        if vision_result["source"] == "vision":
            fallback_name = vision_result["medicine_name"]
            fallback_purpose_ne = vision_result.get("purpose_ne")
            identification_source = "vision"
            # The vision model might have found expiry text where OCR
            # didn't - fold it in so we still try to parse it below.
            ocr_text_for_expiry += "\n" + vision_result.get("raw_text", "")
            vision_expiry = vision_result.get("raw_text", "")  

    # --- Expiry date: attempt regardless of which step identified the medicine ---
    expiry_raw_text = find_expiry_text(ocr_text_for_expiry) or vision_expiry or None

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