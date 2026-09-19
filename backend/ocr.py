# ==============================================================================
# ocr.py
#
# WHAT THIS FILE DOES (in plain words):
# This is STEP 2 of the identification pipeline (see main.py for the full
# picture): reading whatever text is printed on the medicine box/strip, and
# trying to match that text against medicines we already know about.
#
# It's kept in its own file, separate from main.py, so that:
#   - main.py stays focused on "what order do we try things in", while this
#     file stays focused on "how exactly do we read and match text".
#   - If you ever want to improve the matching logic (e.g. handle
#     misspellings, or try a different OCR engine), you only need to touch
#     this one file.
# ==============================================================================

import pytesseract
from PIL import Image


def extract_text_from_image(image: Image.Image) -> str:
    """
    Runs OCR (Optical Character Recognition - i.e. "reading text out of a
    picture") on the given image and returns whatever text it found, as a
    single block of text.

    "nep+eng" tells Tesseract to try recognizing BOTH Devanagari (Nepali)
    and Latin (English) script in the same pass, since medicine packaging
    often mixes both - e.g. an English brand name printed next to Nepali
    usage instructions.

    NOTE: this requires the Nepali language pack to be installed on the
    system (see the setup instructions at the bottom of main.py) - without
    it, this line will raise an error mentioning "nep.traineddata".
    """
    return pytesseract.image_to_string(image, lang="nep+eng")


def match_medicine_from_text(raw_text: str, medicines_by_id: dict) -> str | None:
    """
    Looks through `raw_text` (whatever OCR read off the packaging) for any
    brand name or generic name we recognize from our own medicine database.

    `medicines_by_id` is our loaded medicine_db.json data (id -> info),
    passed in rather than imported directly, so this file doesn't need to
    know WHERE that data came from - it just needs the dictionary to
    search through. This keeps the file reusable and easy to test on its
    own.

    Returns the matching medicine's id (e.g. "paracetamol_500mg") if
    found, or None if nothing in the text matched anything we know.
    """
    lowered_text = raw_text.lower()

    for medicine_id, info in medicines_by_id.items():
        if medicine_id == "_comment":
            continue

        names_to_check = [info["generic_name"]] + info.get("brand_names", [])
        for name in names_to_check:
            if name.lower() in lowered_text:
                return medicine_id

    return None


def try_ocr_lookup(image: Image.Image, medicines_by_id: dict) -> dict:
    """
    The main function main.py actually calls. Combines the two steps
    above (read the text, then try to match it) into one call, and always
    returns a dict - even when nothing matched - because the RAW TEXT is
    still useful afterwards (main.py searches it for an expiry date,
    regardless of whether we recognized the medicine itself).
    """
    raw_text = extract_text_from_image(image)
    matched_medicine_id = match_medicine_from_text(raw_text, medicines_by_id)

    return {
        "source": "ocr" if matched_medicine_id else "ocr_unmatched",
        "medicine_id": matched_medicine_id,
        "raw_text": raw_text,
    }