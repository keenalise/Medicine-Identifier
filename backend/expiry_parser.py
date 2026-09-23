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
#
# WHAT CHANGED vs. THE PREVIOUS VERSION:
#   1. EVERY occurrence of an expiry keyword is checked (before, only the
#      first one was, so a mangled "EXP" early in the text hid a good one).
#   2. Full dates like 05/12/2026 are matched BEFORE shorter ones (before,
#      "05/12/2026" was wrongly returned as just "05/12").
#   3. More separators are accepted: 12/2026, 12-2026, 12.2026, 12 2026.
#   4. Month-name dates are accepted: DEC 2026, Dec.2026, December 2026.
#   5. Search window increased from 20 to 30 characters, so longer labels
#      like "Expiry Date :" don't push the date out of range.
# ==============================================================================

import re

# Words that typically appear right before/near an expiry date on
# packaging, in both English and Nepali. If we see one of these words, we
# know a date is probably nearby.
#
# ORDER MATTERS: longer phrases come first, so "expiry date" is matched as
# a whole before the shorter "expiry" or "exp" get a chance to match part
# of it.
EXPIRY_KEYWORDS = [
    r"expiry\s*date",
    r"exp\.?\s*date",
    r"expiry",
    r"exp\.?",
    r"best\s*before",
    r"best\s*after",
    r"use\s*before",
    r"म्याद\s*सकिने",
    r"म्याद",
]

# All the keywords joined into ONE pattern, so we can find every occurrence
# in the text in a single pass (IGNORECASE handles "EXP", "Exp", "exp").
KEYWORD_PATTERN = re.compile("|".join(EXPIRY_KEYWORDS), re.IGNORECASE)

# Characters allowed BETWEEN the parts of a numeric date: / - . or a space
_SEP = r"[/\-. ]"

# Month names (full or abbreviated), for dates printed like "DEC 2026"
_MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"

# Common ways an expiry date is printed on packaging. The alternatives are
# tried in this order, so the LONGEST/most complete form wins:
#   05/12/2026     (DD/MM/YYYY or DD/MM/YY)
#   12/2026        (MM/YYYY)
#   12/26          (MM/YY)
#   DEC 2026       (month name + year)
#
# (?<!\d) and (?!\d) make sure we don't grab a piece out of the middle of a
# longer number (e.g. part of a batch number).
DATE_PATTERN = re.compile(
    rf"(?<!\d)(?:"
    rf"\d{{1,2}}{_SEP}\d{{1,2}}{_SEP}\d{{2,4}}(?!\d)"   # DD/MM/YYYY
    rf"|\d{{1,2}}{_SEP}\d{{4}}(?!\d)"                    # MM/YYYY
    rf"|\d{{1,2}}{_SEP}\d{{2}}(?!\d)"                    # MM/YY
    rf")"
    rf"|{_MONTHS}[\s.\-/]*\d{{2,4}}(?!\d)",              # DEC 2026
    re.IGNORECASE,
)

# How many characters ahead of an expiry keyword we search for a date. An
# expiry date is almost always printed right after words like "EXP", so 30
# characters is enough room for a date (even after a label like
# "Expiry Date :") without accidentally grabbing an unrelated number
# printed elsewhere on the label.
SEARCH_WINDOW_SIZE = 30


def find_expiry_text(raw_text: str) -> str | None:
    """
    Looks through `raw_text` for expiry-related keywords, and for each one
    searches the nearby text for something that looks like a date.

    Returns the raw matched date text (e.g. "12/2026") for the first
    keyword that has a date next to it, or None if nothing date-like was
    found near any expiry keyword anywhere in the text.
    """
    if not raw_text:
        return None

    # finditer = go through EVERY keyword occurrence in the text, in the
    # order they appear, not just the first one.
    for keyword_match in KEYWORD_PATTERN.finditer(raw_text):
        window_start = keyword_match.end()
        window_text = raw_text[window_start : window_start + SEARCH_WINDOW_SIZE]

        date_match = DATE_PATTERN.search(window_text)
        if date_match:
            # strip() removes stray separators OCR sometimes leaves on the
            # end, e.g. "12/2026." -> "12/2026"
            return date_match.group(0).strip(" .-/")

    return None