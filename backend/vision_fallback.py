# ==============================================================================
# vision_fallback.py
#
# WHAT THIS FILE DOES (in plain words):
# This is STEP 3 of the identification pipeline (see main.py for the full
# picture) - the LAST resort, only used when both the barcode (Step 1) and
# OCR (Step 2) failed to confidently identify the medicine. Common reasons
# Steps 1-2 fail: no barcode on the packaging, worn/creased text, or a
# medicine we simply don't have in our own database yet.
#
# Instead of reading printed text, this step sends the PHOTO ITSELF to an
# AI vision model and asks it to look at the image and describe what
# medicine it thinks this is - similar to how a person could recognize a
# familiar medicine box by its look, even with damaged text.
#
# This step needs TWO things to actually work:
#   1. Internet access (this app is online-only for now, per the plan).
#   2. A free Gemini API key, set as GEMINI_API_KEY (see .env.example).
# If either is missing, this file fails gracefully and says so, rather
# than crashing the whole /scan request.
# ==============================================================================

import json
from PIL import Image

import google.generativeai as genai


# The exact instructions given to the vision model. Asking for ONLY a JSON
# object (no extra sentences) makes the reply easy and reliable to parse in
# code, instead of us trying to make sense of a free-form paragraph.
PROMPT = (
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


def create_vision_model(api_key: str | None):
    """
    Sets up the connection to the vision model, using the given API key.

    Returns the ready-to-use model object, or None if no API key was
    given. Returning None (instead of raising an error) is deliberate -
    it lets the rest of the app keep working without Step 3, for anyone
    who hasn't set up a Gemini key yet, rather than forcing it to be
    required from day one.

    Call this ONCE when the server starts (see main.py), not on every
    single request - there's no need to redo this setup each time.
    """
    if not api_key:
        return None

    genai.configure(api_key=api_key)

    # NOTE: Google renames/updates their free-tier model names occasionally.
    # "gemini-1.5-flash" is correct as of this writing, but if this line
    # errors out with a "model not found" message, check
    # https://ai.google.dev/gemini-api/docs/models for the current free
    # model name and update the string below.
    return genai.GenerativeModel("gemini-1.5-flash")


def try_vision_fallback(image: Image.Image, vision_model) -> dict:
    """
    Sends `image` to the vision model (created earlier with
    create_vision_model) and asks it to identify the medicine.

    `vision_model` is passed in rather than created inside this function,
    so the (somewhat slow) setup step only ever happens once at server
    startup, not on every photo a user submits.

    Always returns a dict describing what happened - including WHY it
    didn't work, if it didn't - so the caller (and eventually the person
    using the app) never gets a silent, unexplained failure:
      - "vision_unavailable" -> no API key was configured at all
      - "vision_error"       -> the request failed (no internet, rate
                                 limit reached on the free tier, or a
                                 reply we couldn't understand)
      - "vision"              -> success, with a genuine answer
    """
    if vision_model is None:
        return {"source": "vision_unavailable", "medicine_name": None, "raw_text": ""}

    try:
        response = vision_model.generate_content([PROMPT, image])
        # The model sometimes wraps JSON in ```json ... ``` even when asked
        # not to - this strips that off before parsing, just in case.
        cleaned = response.text.strip().strip("`").removeprefix("json").strip()
        parsed = json.loads(cleaned)
    except Exception:
        # Could be a network error, a rate-limit (free tier), or the model
        # replying in a format we couldn't parse. Either way, we fail
        # gracefully rather than crashing the whole /scan request.
        return {"source": "vision_error", "medicine_name": None, "raw_text": ""}

    return {
        "source": "vision",
        "medicine_name": parsed.get("medicine_name") or None,
        "purpose_ne": parsed.get("purpose_ne") or None,
        "raw_text": parsed.get("expiry_text") or "",
    }
