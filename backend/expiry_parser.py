# ==============================================================================
# expiry_parser.py
#
# WHAT THIS FILE DOES (in plain words):
# This file has ONE job: given a block of text (from OCR, or from the
# vision model), find the part that looks like an EXPIRY DATE and return
# it. It's used regardless of which step (barcode/OCR/vision) actually
# identified the medicine - expiry-date reading is a separate concern from
# "what medicine is this", so it lives in its own file.
#
# IMPORTANT DESIGN CHOICE: this file returns the RAW matched text (e.g.
# "12/2026"), not a cleaned-up/converted date. We deliberately do NOT try
# to be clever and silently convert it ourselves. The frontend shows this
# raw text back to the user next to the big ✅/❌ confirm buttons, so THEY
# confirm it's correct - reducing the chance of a wrong guess (e.g.
# misreading "12/2026" as "1/2/2026") reaching someone who can't easily
# double-check it themselves.
# ==============================================================================

import re

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
#   05/12/2026      (DD/MM/YYYY)
DATE_PATTERN = re.compile(
    r"(\d{1,2}[/\-]\d{4})|(\d{1,2}[/\-]\d{2})(?!\d)|(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})"
)

# How many characters ahead of an expiry keyword we search for a date. An
# expiry date is almost always printed right after words like "EXP", so 20
# characters is enough room for a date without accidentally grabbing an
# unrelated number printed elsewhere on the label.
SEARCH_WINDOW_SIZE = 20


def find_expiry_text(raw_text: str) -> str | None:
    """
    Looks through `raw_text` for an expiry-related keyword, and if found,
    searches the nearby text for something that looks like a date.

    Returns the raw matched date text (e.g. "12/2026") if found, or None
    if nothing date-like was found near an expiry keyword anywhere in the
    text.
    """
    if not raw_text:
        return None

    lowered = raw_text.lower()

    for keyword in EXPIRY_KEYWORDS:
        keyword_match = re.search(keyword, lowered)
        if not keyword_match:
            continue

        window_start = keyword_match.end()
        window_text = raw_text[window_start : window_start + SEARCH_WINDOW_SIZE]

        date_match = DATE_PATTERN.search(window_text)
        if date_match:
            return date_match.group(0)

    return None
