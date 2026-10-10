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
#
# WHY THERE ARE SEVERAL OCR PASSES:
# A single Tesseract call on a phone photo of a foil strip reliably reads
# the big brand name but very often MISSES the expiry date: the date line
# is tiny, printed sideways along the edge of the strip, and runs across the
# shiny blister bumps. On the sample strip in this repo one plain pass
# returned "MEG 21 JUN.2" - the manufacturing date with its year chopped
# off, and no expiry at all. So this file reads the image in stages and
# stops as soon as a complete expiry date shows up:
#   1. one plain pass (fast, catches most boxes),
#   2. a "zoomed-in" pass: find the words that look like part of a date
#      line (month names, MFG/EXP, a year), crop a thin band around that
#      line, enlarge it 2x and re-read ONLY that band - small text is far
#      easier for Tesseract when it fills the frame,
#   3. the same two steps again with the photo rotated, for strips held
#      sideways or upside down.
# Every pass's text is kept, so the medicine-name match can use all of
# them, and main.py picks the most trustworthy expiry among them.
# ==============================================================================

import re

import pytesseract
from pytesseract import Output
from PIL import Image, ImageOps

from expiry_parser import analyze_expiry, expiry_confidence

# Phone photos can be 4000 px wide; Tesseract gets slower (not better) past
# ~2000 px on the long side, so bigger images are shrunk first.
MAX_OCR_SIDE = 2000

# Zoom factor for the date-line re-read. 2x was the sweet spot on real
# strips; 3x-4x started to break the digits apart again.
DATE_BAND_SCALE = 2

# Words that mark a date line: month names (English or Nepali), the
# Mfg/Exp labels, or a 20xx year. Used to find WHERE the date line is.
_DATE_WORD = re.compile(
    r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|m[fe6&]g|mfd|ex[pf]|20\d\d"
    r"|जनवरी|फेब्रु|मार्च|अप्रिल|जुन|जुलाई|अगस्ट|सेप्टेम्बर|अक्टोबर|नोभेम्बर|डिसेम्बर"
    r"|म्याद|निर्माण|२०\d\d)",
    re.IGNORECASE,
)

# The confidence score (see expiry_parser.expiry_confidence) at which we
# stop doing more OCR passes: an explicit EXP label with a complete date.
_GOOD_ENOUGH = expiry_confidence("exp_keyword", "12/2026")


def _shrink_for_ocr(image: Image.Image) -> Image.Image:
    longest = max(image.size)
    if longest <= MAX_OCR_SIDE:
        return image
    ratio = MAX_OCR_SIDE / longest
    return image.resize(
        (max(1, round(image.width * ratio)), max(1, round(image.height * ratio))),
        Image.LANCZOS,
    )


def _ocr(image: Image.Image, lang: str = "nep+eng", psm: int = 3) -> str:
    """One Tesseract call. Never raises on an empty result - returns ""."""
    try:
        return pytesseract.image_to_string(image, lang=lang, config=f"--psm {psm}")
    except pytesseract.TesseractError:
        return ""


def _date_line_boxes(image: Image.Image, lang: str = "nep+eng") -> list:
    """
    Runs Tesseract in "give me every word with its position" mode and
    returns the bounding box of each text LINE that contains a date-looking
    word, as (left, top, right, bottom, is_vertical).

    is_vertical is True when the line is taller than it is wide - i.e. the
    text is printed sideways along the strip (Tesseract still reads such
    lines, but reports them in the photo's own coordinates).
    """
    try:
        data = pytesseract.image_to_data(image, lang=lang, output_type=Output.DICT)
    except pytesseract.TesseractError:
        return []

    lines: dict = {}
    for i, word in enumerate(data["text"]):
        word = word.strip()
        if not word:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        left, top = data["left"][i], data["top"][i]
        right, bottom = left + data["width"][i], top + data["height"][i]
        line = lines.setdefault(key, [left, top, right, bottom, False])
        line[0] = min(line[0], left)
        line[1] = min(line[1], top)
        line[2] = max(line[2], right)
        line[3] = max(line[3], bottom)
        if _DATE_WORD.search(word):
            line[4] = True

    boxes = []
    for left, top, right, bottom, has_date_word in lines.values():
        if not has_date_word:
            continue
        is_vertical = (bottom - top) > (right - left)
        boxes.append((left, top, right, bottom, is_vertical))
    return boxes


def _read_date_bands(image: Image.Image) -> list:
    """
    The "zoom in on the date line" pass. For every line that contains a
    date-looking word, crops a band around it spanning the WHOLE image
    (because the first pass usually read only the start of the line and
    chopped off the end - "MFG.21 JUN.2026 EXP.20 JUN.2029" came back as
    "MEG 21 JUN.2"), enlarges it and reads it again with Tesseract told to
    expect a single block / single line of text.

    Sideways lines are rotated upright before reading; since we can't tell
    which way is "up" from the box alone, both directions are tried.

    Returns the list of texts read (possibly empty).
    """
    texts = []
    for left, top, right, bottom, is_vertical in _date_line_boxes(image):
        if is_vertical:
            pad = max(8, (right - left) // 4)
            band = image.crop((max(0, left - pad), 0, min(image.width, right + pad), image.height))
            candidates = [band.rotate(90, expand=True), band.rotate(270, expand=True)]
        else:
            pad = max(8, (bottom - top) // 2)
            band = image.crop((0, max(0, top - pad), image.width, min(image.height, bottom + pad)))
            candidates = [band]

        for strip in candidates:
            gray = ImageOps.grayscale(strip)
            gray = gray.resize(
                (gray.width * DATE_BAND_SCALE, gray.height * DATE_BAND_SCALE), Image.LANCZOS
            )
            # psm 6 = "one uniform block of text", psm 13 = "raw line, no
            # layout analysis". On foil strips they fail in different ways,
            # so both are kept; expiry_parser picks the better result.
            # English-only here on purpose: on a zoomed foil band the
            # Devanagari model turns glare into runs of digits that LOOK like
            # dates. Nepali-script dates are still caught by the full-image
            # "nep+eng" pass in stage 1.
            for psm in (6, 13):
                text = _ocr(gray, lang="eng", psm=psm)
                if text.strip():
                    texts.append(text)
    return texts


def _best_score(texts: list) -> int:
    return max((expiry_confidence(*analyze_expiry(t)) for t in texts), default=0)


def extract_texts_from_image(image: Image.Image) -> list:
    """
    Runs the staged OCR described at the top of this file and returns EVERY
    text block it read, in the order read. The first entry is always the
    plain full-image pass.

    "nep+eng" tells Tesseract to try recognizing BOTH Devanagari (Nepali)
    and Latin (English) script in the same pass, since medicine packaging
    often mixes both - e.g. an English brand name printed next to Nepali
    usage instructions.

    NOTE: this requires the Nepali language pack to be installed on the
    system (see the setup instructions at the bottom of main.py) - without
    it, this will raise an error mentioning "nep.traineddata".
    """
    base = _shrink_for_ocr(image)

    # Stage 1: plain pass on the photo as uploaded.
    texts = [pytesseract.image_to_string(base, lang="nep+eng")]
    if _best_score(texts) >= _GOOD_ENOUGH:
        return texts

    # Stage 2: zoom in on whatever date line stage 1 glimpsed.
    texts += _read_date_bands(base)
    if _best_score(texts) >= _GOOD_ENOUGH:
        return texts

    # Stage 3: the strip may be sideways relative to the photo. Tesseract's
    # own layout analysis copes with most rotated text (stages 1-2 found the
    # sideways date line on the sample strip without any rotation), so this
    # slow last resort only runs when NOTHING date-like was found at all.
    if _best_score(texts) == 0:
        for angle in (90, 270):
            rotated = base.rotate(angle, expand=True)
            texts.append(_ocr(rotated))
            texts += _read_date_bands(rotated)
            if _best_score(texts) >= _GOOD_ENOUGH:
                break

    return [t for t in texts if t and t.strip()]


def extract_text_from_image(image: Image.Image) -> str:
    """
    Convenience wrapper: all OCR passes joined into one block of text. Kept
    for callers that only need "whatever text is on the packaging".
    """
    return "\n".join(extract_texts_from_image(image))


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

    "texts" is the list of individual OCR passes (see
    extract_texts_from_image); "raw_text" is all of them joined.
    """
    texts = extract_texts_from_image(image)
    raw_text = "\n".join(texts)
    matched_medicine_id = match_medicine_from_text(raw_text, medicines_by_id)

    return {
        "source": "ocr" if matched_medicine_id else "ocr_unmatched",
        "medicine_id": matched_medicine_id,
        "raw_text": raw_text,
        "texts": texts,
    }
