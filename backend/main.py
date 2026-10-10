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
import logging
import time

from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import Response
from gtts import gTTS
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageOps
from pyzbar.pyzbar import decode as decode_barcodes
from dotenv import load_dotenv

from ocr import try_ocr_lookup, match_medicine_from_text
from vision_fallback import (
    create_vision_model,
    try_vision_fallback,
    try_extract_expiry_date,
)
from expiry_parser import (
    analyze_expiry_texts,
    expiry_is_after_mfg,
    format_expiry_for_speech,
    format_expiry_in_nepali,
    is_complete_date,
    strip_expiry_label,
)

# Loads the GEMINI_API_KEY (and any other secrets) from a local ".env" file,
# if one exists. See .env.example for what variable names are expected.
load_dotenv()

# ------------------------------------------------------------------------
# App setup
# ------------------------------------------------------------------------

app = FastAPI(title="Medicine Identifier Backend")

# One line per scan in the server console saying what each step found and
# how long it took - the quickest way to tell "OCR missed it", "vision was
# rate-limited" and "the phone sent a bad photo" apart.
logging.basicConfig(level=logging.INFO, format="%(levelname)s [%(name)s] %(message)s")
logger = logging.getLogger("scan")

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
# at server startup and makes no network request.
#
# NOTE: since 2026 Google AI Studio only issues the new "AQ..." style Auth
# keys, which DO work with this setup. The model names live in
# vision_fallback.py (VISION_MODEL_NAMES).
# ------------------------------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
_vision_model = create_vision_model(GEMINI_API_KEY)

if _vision_model is None:
    print("[vision] Gemini vision model DISABLED - no GEMINI_API_KEY in .env.")
else:
    # Deliberately NO test request here: the free tier allows only ~20
    # requests per model per DAY, and a check on every (auto)restart would
    # eat into that. Problems with the key or model names show up in the
    # log on the first scan instead (see vision_fallback.py).
    print("[vision] Gemini vision model ENABLED - expiry date read with computer vision.")


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
        image = Image.open(io.BytesIO(image_bytes))
        # Phone cameras store the photo sideways and record the real
        # orientation in EXIF metadata. PIL ignores that unless asked, and
        # Tesseract cannot read a sideways photo - so rotate it upright first.
        image = ImageOps.exif_transpose(image).convert("RGB")
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read the uploaded image")

    started_at = time.monotonic()
    medicine_id = None
    identification_source = None
    fallback_name = None  # used when the vision model names a medicine
    fallback_name_ne = None  # ditto, in Nepali
    fallback_purpose_ne = None  # used when the vision model describes it
    ocr_text_for_expiry = ""  # whatever text we gather along the way
    vision_expiry = ""
    vision_mfg = ""

    # --- STEP 1: barcode ---
    barcode_result = try_barcode_lookup(image)
    if barcode_result and barcode_result["medicine_id"]:
        medicine_id = barcode_result["medicine_id"]
        identification_source = "barcode"

    # --- STEP 2: OCR (always run, so we can read the expiry date) ---
    ocr_result = try_ocr_lookup(image, MEDICINES_BY_ID)
    ocr_text_for_expiry = ocr_result["raw_text"]
    ocr_seconds = time.monotonic() - started_at
    if medicine_id is None and ocr_result["medicine_id"]:
        medicine_id = ocr_result["medicine_id"]
        identification_source = "ocr"

    # --- STEP 3: vision model fallback (only if steps 1 and 2 both failed) ---
    vision_identify_source = "skipped"
    if medicine_id is None:
        vision_result = try_vision_fallback(image, _vision_model)
        vision_identify_source = vision_result["source"]
        if vision_result["source"] == "vision":
            identification_source = "vision"
            # The model usually names the BRAND ("Niko") and, separately,
            # the generic name ("Paracetamol"). If either is a medicine we
            # know, answer from our own database - same name, same purpose
            # text, same as when OCR identifies it - so the result doesn't
            # depend on which step happened to succeed.
            for candidate in (vision_result.get("generic_name"), vision_result.get("medicine_name")):
                if candidate:
                    medicine_id = match_medicine_from_text(candidate, MEDICINES_BY_ID)
                    if medicine_id:
                        break
            if medicine_id is None:
                # Not in our database: show the model's own answer, generic
                # name first (more useful than a brand), brand as fallback.
                fallback_name = vision_result.get("generic_name") or vision_result["medicine_name"]
                fallback_name_ne = vision_result.get("medicine_name_ne")
                fallback_purpose_ne = vision_result.get("purpose_ne")
            # The vision model might have read an expiry date where OCR
            # didn't - keep it around; it's used in the expiry section below.
            vision_expiry = vision_result.get("raw_text") or ""
            vision_mfg = vision_result.get("mfg_text") or ""

    # --- Expiry date: attempt regardless of which step identified the medicine ---
    #
    # OCR often reads the dates on a package but drops the little labels
    # ("EXP"/"म्याद" vs "Mfg"/"निर्माण"), so it can confuse the
    # MANUFACTURING date with the EXPIRY date, AND it often chops digits off
    # the end of a date (e.g. "20 JUNE 2029" -> "21 JUN.2"). The expiry date
    # is a SENSITIVE field - showing a wrong/half-read date is worse than
    # showing none - so OCR's answer is only used when it is BOTH:
    #   - found next to a real expiry keyword, or floating in the text with
    #     no label at all (never a manufacturing-only date); AND
    #   - a complete date with a full 2/4-digit year (is_complete_date).
    # When the date is uncertain, missing, or incomplete AND a vision model
    # is configured, we ask the model directly - it reads the printed
    # "Exp./म्याद" label and full date far more reliably than Tesseract.
    expiry_source, ocr_expiry = analyze_expiry_texts(
        ocr_result.get("texts") or [ocr_text_for_expiry]
    )
    ocr_expiry_is_usable = (
        expiry_source in ("exp_keyword", "fallback") and is_complete_date(ocr_expiry)
    )
    ocr_expiry_is_certain = expiry_source == "exp_keyword" and ocr_expiry_is_usable
    expiry_raw_text = None
    vision_expiry_source = "skipped"

    # Cross-check: if OCR read a date next to a "MFG" label, any expiry we
    # show must be later than it. A vision answer that isn't is a blend of
    # the two printed dates (a blurry-photo failure) - drop it and let the
    # focused date prompt below have a go.
    ocr_mfg = ocr_expiry if expiry_source == "mfg_keyword" else None
    if vision_expiry and expiry_is_after_mfg(vision_expiry, ocr_mfg or vision_mfg) is False:
        logger.warning("vision expiry %r not after mfg %r - dropped", vision_expiry, ocr_mfg or vision_mfg)
        vision_expiry = ""

    if vision_expiry:
        # The STEP-3 vision run already read an expiry date - use it.
        expiry_raw_text = vision_expiry
    elif ocr_expiry_is_certain:
        # OCR found a complete date right after an "EXP"/"म्याद" label - no
        # need to spend a (slow, rate-limited) vision call on it.
        expiry_raw_text = ocr_expiry
    elif _vision_model is not None:
        # OCR's date is missing, unlabeled, or has a chopped year (e.g.
        # "20 JUN.2"): ask the model directly - it reads the printed
        # "Exp./म्याद" label and full date far more reliably than Tesseract.
        expiry_vision = try_extract_expiry_date(image, _vision_model)
        vision_expiry_source = expiry_vision["source"]
        candidate = expiry_vision.get("expiry_text")
        if candidate and expiry_is_after_mfg(candidate, ocr_mfg) is False:
            logger.warning("vision expiry %r not after OCR mfg %r - dropped", candidate, ocr_mfg)
            candidate = None
        if candidate:
            expiry_raw_text = candidate
        elif ocr_expiry_is_usable:
            # The model couldn't answer (offline/rate limit) - fall back to
            # OCR's date, which is at least complete.
            expiry_raw_text = ocr_expiry
    elif ocr_expiry_is_usable:
        expiry_raw_text = ocr_expiry
    # else: only a manufacturing date, or incomplete/garbled OCR text - keep
    # it None. Never show such a value as the expiry date.

    # The vision model sometimes copies the label along with the date
    # ("EXP.20 JUN.2029"); keep just the date part for display.
    expiry_raw_text = strip_expiry_label(expiry_raw_text)

    # The same date, converted to Nepali-friendly text (Devanagari digits &
    # Nepali month names) purely for display, e.g. "21 JUN 2026" -> "२१ जुन २०२६".
    expiry_text_ne = format_expiry_in_nepali(expiry_raw_text)

    # --- Build the final answer ---
    if medicine_id:
        info = MEDICINES_BY_ID[medicine_id]
        result = {
            "identified": True,
            "source": identification_source,
            "generic_name": info["generic_name"],
            "generic_name_ne": info.get("generic_name_ne") or None,
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
            "generic_name_ne": fallback_name_ne,
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
            "generic_name_ne": None,
            "purpose_ne": None,
            "purpose_en": None,
        }

    logger.info(
        "photo %sx%s | ocr %.1fs medicine=%s expiry=%s %r | vision identify=%s expiry=%s | "
        "result identified=%s name=%r expiry=%r | %.1fs total",
        image.width, image.height, ocr_seconds, ocr_result["medicine_id"],
        expiry_source, ocr_expiry, vision_identify_source, vision_expiry_source,
        result["identified"], result["generic_name"], expiry_raw_text,
        time.monotonic() - started_at,
    )

    result["expiry_raw_text"] = expiry_raw_text  # e.g. "12/2026", or None
    result["expiry_text_ne"] = expiry_text_ne  # e.g. "१२/२०२६", or None
    # Ready-made sentences for the "listen" button (text-to-speech), one
    # per language, so both apps read out exactly the same thing. Built
    # here rather than in each app so the wording lives in one place.
    result["speech_text_ne"] = build_speech_text(result, expiry_raw_text, "ne")
    result["speech_text_en"] = build_speech_text(result, expiry_raw_text, "en")
    # This tells the frontend: always show the big ✅/❌ confirm buttons,
    # never treat a guess (from ANY of the 3 steps) as final on its own.
    result["needs_user_confirmation"] = True

    return result


def build_speech_text(result: dict, expiry_raw_text: str | None, language: str) -> str:
    """
    Composes what the "listen" button says, in Nepali ("ne") or English
    ("en"): the medicine's name, what it is for, and the expiry date - or
    an honest "could not identify / could not read" when a part is missing.
    """
    expiry_spoken = format_expiry_for_speech(expiry_raw_text, language)
    parts = []
    if language == "ne":
        if result["identified"]:
            parts.append(result.get("generic_name_ne") or result.get("generic_name") or "")
            if result.get("purpose_ne"):
                parts.append(f"यो औषधि {result['purpose_ne']}")
        else:
            parts.append("औषधि पत्ता लगाउन सकिएन")
        parts.append(
            f"म्याद सकिने मिति {expiry_spoken}" if expiry_spoken else "म्याद सकिने मिति पढ्न सकिएन"
        )
    else:
        if result["identified"]:
            parts.append(result.get("generic_name") or result.get("generic_name_ne") or "")
            purpose = result.get("purpose_en") or result.get("purpose_ne")
            if purpose:
                parts.append(purpose)
        else:
            parts.append("The medicine could not be identified")
        parts.append(
            f"Expiry date {expiry_spoken}" if expiry_spoken else "The expiry date could not be read"
        )
    return "। ".join(p.strip(" ।.") for p in parts if p) + "।" if language == "ne" \
        else ". ".join(p.strip(" .") for p in parts if p) + "."


# ------------------------------------------------------------------------
# Text-to-speech: GET /speak?lang=ne&text=... returns an MP3 of the text,
# spoken in Nepali or English. Uses gTTS (Google Translate's free speech
# service - no key needed) because phone and browser voices very rarely
# include Nepali, while this one does. Needs internet, like the vision step.
# Each sentence is synthesised once and kept in memory, so pressing the
# button again (or the second app asking for the same sentence) is instant.
# ------------------------------------------------------------------------

SPEECH_LANGUAGES = {"ne", "en"}
SPEECH_MAX_CHARS = 600
_speech_cache: dict = {}
_SPEECH_CACHE_LIMIT = 200


@app.get("/speak")
async def speak(
    text: str = Query(..., min_length=1, max_length=SPEECH_MAX_CHARS),
    lang: str = Query("ne"),
):
    if lang not in SPEECH_LANGUAGES:
        raise HTTPException(status_code=400, detail="lang must be 'ne' or 'en'")
    cache_key = (lang, text)
    audio = _speech_cache.get(cache_key)
    if audio is None:
        try:
            buffer = io.BytesIO()
            gTTS(text=text, lang=lang).write_to_fp(buffer)
            audio = buffer.getvalue()
        except Exception as error:
            logger.warning("speech synthesis failed: %s: %s", type(error).__name__, str(error)[:200])
            raise HTTPException(status_code=502, detail="Speech service unavailable")
        if len(_speech_cache) >= _SPEECH_CACHE_LIMIT:
            _speech_cache.pop(next(iter(_speech_cache)))
        _speech_cache[cache_key] = audio
    return Response(content=audio, media_type="audio/mpeg", headers={"Cache-Control": "public, max-age=86400"})


# ------------------------------------------------------------------------
# A tiny endpoint just to check the server is alive - useful for the
# frontend (or you, in a browser) to quickly confirm the backend is
# actually running, without needing to test the full photo-upload flow.
# ------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "vision_enabled": _vision_model is not None,
        # Per-model view: "available" or "resting until HH:MM" when that
        # model's daily free-tier quota is used up.
        "vision_models": _vision_model.status() if _vision_model is not None else {},
    }


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
#    app still runs without it, it just can't do Step 3 / vision fallback,
#    and its expiry-date reading falls back to OCR alone).
#    Get a free key from https://aistudio.google.com/apikey (2026: AI Studio
#    now issues "AQ..." Auth keys - they work fine here). If the server still
#    reports the vision model DISABLED, the model name in vision_fallback.py
#    is probably outdated for the current year - update it.
#
# 4. Start the server:
#      uvicorn main:app --reload --port 8000
#
#    Then the frontend's TODO (backend step) comments in app/page.jsx
#    should call: http://localhost:8000/scan
# ==============================================================================