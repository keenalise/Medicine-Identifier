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
# WHY THE "WHOLE-TEXT FALLBACK" EXISTS:
# Real-world OCR is lossy. On an actual photo, Tesseract may read the
# expiry date itself ("21 JUN.2026") but drop the little label word that
# comes before it ("EXP", "Mfg", "म्याद", ...). Older versions of this file
# returned nothing in that situation, which is exactly the bug the user
# reported: the date was in the text, but we didn't look for it unless an
# expiry keyword was also found. The fix is to search the WHOLE text for a
# date as a second pass - but only with "strong" date shapes (a full-ish
# date like 21/06/2026, 12/2026, DEC 2026), so we don't accidentally return
# an unrelated number such as a price ("10.00") or a batch number.
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
    r"mfg\.?\s*date",
    r"expiry",
    r"exp\.?",
    r"mfg\.?",
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

# "Strong" date shapes - the ones we trust enough to match NOT only right
# after an expiry keyword, but ANYWHERE in the text:
#   21/06/2026, 21-06-26   (DD/MM/YYYY or DD/MM/YY)
#   12/2026                (MM/YYYY)
#   21 JUN 2026, 21 JUN.2  (day + month name + year)
#   DEC 2026               (month name + year)
#
# The alternatives are tried in this order, so the LONGEST/most complete
# form wins.
#
# (?<!\d) and (?!\d) make sure we don't grab a piece out of the middle of a
# longer number (e.g. part of a batch number).
_STRONG_DATE_PATTERN = re.compile(
    rf"(?<!\d)(?:"
    rf"\d{{1,2}}{_SEP}\d{{1,2}}{_SEP}\d{{2,4}}(?!\d)"   # DD/MM/YYYY, DD/MM/YY
    rf"|\d{{1,2}}{_SEP}\d{{4}}(?!\d)"                    # MM/YYYY
    rf"|\d{{1,2}}\s*{_MONTHS}[\s.\-/]*\d{{1,4}}(?!\d)"  # 21 JUN 2026 / 21 JUN.2
    rf"|{_MONTHS}[\s.\-/]*\d{{2,4}}(?!\d)"               # DEC 2026
    rf")",
    re.IGNORECASE,
)

# "Weak" date shape - ONLY trusted when it appears right after an expiry
# keyword, because a bare "MM/YY" like "10.00" also looks like a price and
# could otherwise be a false positive all on its own:
#   12/26                 (MM/YY)
_WEAK_DATE_PATTERN = re.compile(
    rf"(?<!\d)\d{{1,2}}{_SEP}\d{{2}}(?!\d)"
)

# How many characters ahead of an expiry keyword we search for a date. An
# expiry date is almost always printed right after words like "EXP", so 30
# characters is enough room for a date (even after a label like
# "Expiry Date :") without accidentally grabbing an unrelated number
# printed elsewhere on the label.
SEARCH_WINDOW_SIZE = 30


def _clean_match(match: re.Match) -> str:
    # strip() removes stray separators OCR sometimes leaves on the end,
    # e.g. "12/2026." -> "12/2026"
    return match.group(0).strip(" .-/")


def _match_near_keyword(raw_text: str, pattern: re.Pattern) -> str | None:
    """
    Searches for `pattern` in the text right before each expiry keyword.

    Keywords are checked from LAST to FIRST (reversed), not first to last.
    Reason: packaging usually prints "Mfg. date" and THEN "Exp. date" next
    to it, so when several date-like matches exist the one after the LAST
    keyword is most likely the expiry and the one before it the mfg date.
    Returns the cleaned first hit, or None if no keyword has a nearby date.
    """
    for keyword_match in reversed(list(KEYWORD_PATTERN.finditer(raw_text))):
        window_start = keyword_match.end()
        window_text = raw_text[window_start : window_start + SEARCH_WINDOW_SIZE]
        date_match = pattern.search(window_text)
        if date_match:
            return _clean_match(date_match)
    return None


def find_expiry_text(raw_text: str) -> str | None:
    """
    Looks through `raw_text` for an expiry date and returns it as raw text
    (e.g. "12/2026"), or None if nothing date-like was found.

    Three passes, in order of how much we trust the result:
      1. A strong date right after an expiry keyword (the clearest signal).
      2. A weak "MM/YY" date after an expiry keyword (e.g. "EXP 09/26").
      3. A strong date ANYWHERE in the text - the fallback for when OCR
         read the date but dropped the "EXP"/"Mfg" label in front of it
         (this was the bug that made the expiry date come back empty).
    """
    if not raw_text:
        return None

    # Pass 1: clear expiry keyword + a strong, full-looking date.
    matched = _match_near_keyword(raw_text, _STRONG_DATE_PATTERN)
    if matched:
        return matched

    # Pass 2: a weak MM/YY date, but only right after an expiry keyword.
    matched = _match_near_keyword(raw_text, _WEAK_DATE_PATTERN)
    if matched:
        return matched

    # Pass 3: whole-text fallback - OCR often keeps the date while losing
    # the label in front of it. Strong shapes only, see header comment.
    date_match = _STRONG_DATE_PATTERN.search(raw_text)
    if date_match:
        return _clean_match(date_match)

    return None