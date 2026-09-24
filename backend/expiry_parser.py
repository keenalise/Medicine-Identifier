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
# MANUFACTURING DATE vs EXPIRY DATE:
# Medicine packaging prints BOTH "Mfg/निर्माण Date" AND "ExP/म्याद Date".
# They are different dates, and mislabeling the manufacturing date as the
# expiry date is dangerous. So this file treats the two kinds of keyword
# separately:
#   - a date found next to an EXPIRY keyword  -> trusted ("exp_keyword")
#   - a date found next to a MANUFACTURING keyword -> NOT the expiry
#     ("mfg_keyword") - the caller must not present it as one.
#   - a date found floating in the text with neither label ("fallback") ->
#     returned, but flagged, because OCR often drops the little "EXP"
#     label while keeping the date itself.
#
# NEPALI DISPLAY:
# format_expiry_in_nepali() turns the raw matched text ("21 JUN 2026",
# "12/2026") into a Nepali-friendly version using Devanagari digits and
# Nepali month names ("२१ जुन २०२६", "१२/२०२६"). The Nepali version is
# meant for DISPLAY only - the raw text is what gets confirmed/corrected.
# ==============================================================================

import re

# Words that mean "the expiry date is around here" - English and Nepali.
#
# ORDER MATTERS: longer phrases come first, so "expiry date" is matched as
# a whole before the shorter "expiry" or "exp" get a chance to match part
# of it.
EXPIRY_KEYWORDS = [
    r"expiry\s*date",
    r"exp\.?\s*date",
    r"expiration\s*date",
    r"expires?\s*on",
    r"expiry",
    r"expiration",
    r"exp\.?",
    r"valid\s*until",
    r"valid\s*thru",
    r"valid\s*up\s*to",
    r"use\s*by\s*date",
    r"use\s*by",
    r"use\s*before",
    r"best\s*before",
    r"best\s*by",
    r"best\s*after",
    r"सकिने\s*मिति",
    r"म्याद\s*सकिने",
    r"म्याद",
    r"समाप्ति\s*मिति",
    r"अन्तिम\s*मिति",
    r"प्रयोग\s*नगर्ने\s*मिति",
]

# Words that mean "this is the MANUFACTURING (made-on) date" - we must NOT
# present one of these dates as the expiry date.
MANUFACTURE_KEYWORDS = [
    r"manufacturing\s*date",
    r"manufactured",
    r"manufacture",
    r"mfg\.?\s*date",
    r"mfg\.?",
    r"mfd\.?",
    r"production\s*date",
    r"prod\.?\s*date",
    r"निर्माण\s*मिति",
    r"उत्पादन\s*मिति",
    r"बनाइएको\s*मिति",
    r"बनेको\s*मिति",
]

# All the keywords joined into ONE pattern each, so we can find every
# occurrence in a single pass (IGNORECASE handles "EXP", "Exp", "exp").
EXPIRY_KEYWORD_PATTERN = re.compile("|".join(EXPIRY_KEYWORDS), re.IGNORECASE)
MANUFACTURE_KEYWORD_PATTERN = re.compile("|".join(MANUFACTURE_KEYWORDS), re.IGNORECASE)

# Characters allowed BETWEEN the parts of a numeric date: / - . or a space
_SEP = r"[/\-. ]"

# Month names, for dates printed like "DEC 2026", "जुन 2029" or "असार 2082".
# Note: Python's \d already matches Devanagari digits (०-९), so dates like
# "२० जुन २०२९" are handled by the same patterns as "20 JUN 2029".
_LATIN_MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*"
_DEVANAGARI_MONTHS = (
    r"(?:जनवरी|फेब्रुवरी|फेब्रुअरी|मार्च|अप्रिल|मे|जुन|जुलाई|अगस्ट|अगस्त|"
    r"सेप्टेम्बर|अक्टोबर|नोभेम्बर|डिसेम्बर|"
    r"वैशाख|बैशाख|जेठ|असार|साउन|भदौ|भाद्र|असोज|कात्तिक|कार्तिक|"
    r"मंसिर|मङ्सिर|पुस|पुष|माघ|फागुन|चैत)"
)
_MONTHS = rf"(?:{_LATIN_MONTHS}|{_DEVANAGARI_MONTHS})"

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

# How many characters ahead of a keyword we search for a date. A date is
# almost always printed right after words like "EXP" / "म्याद", so 30
# characters is enough room (even after a label like "Expiry Date :")
# without accidentally grabbing an unrelated number printed elsewhere.
SEARCH_WINDOW_SIZE = 30

# Mapping from English month abbreviation to the Nepali month name, used by
# format_expiry_in_nepali() to turn "21 JUN 2026" into "२१ जुन २०२६".
_MONTHS_NE = {
    "jan": "जनवरी",
    "feb": "फेब्रुअरी",
    "mar": "मार्च",
    "apr": "अप्रिल",
    "may": "मे",
    "jun": "जुन",
    "jul": "जुलाई",
    "aug": "अगस्ट",
    "sep": "सेप्टेम्बर",
    "oct": "अक्टोबर",
    "nov": "नोभेम्बर",
    "dec": "डिसेम्बर",
}

# Regular digits -> Devanagari digits (0-9 -> ०-९), for the Nepali display.
_DIGITS_NE = str.maketrans("0123456789", "०१२३४५६७८९")


def _clean_match(match: re.Match) -> str:
    # strip() removes stray separators OCR sometimes leaves on the end,
    # e.g. "12/2026." -> "12/2026"
    return match.group(0).strip(" .-/")


def _date_near_keyword(
    raw_text: str, keyword_pattern: re.Pattern, allow_weak: bool = True
) -> str | None:
    """
    Searches for a date in the text right before each occurrence of the
    given keyword.

    Keywords are checked from LAST to FIRST (reversed), not first to last.
    Reason: packaging usually prints "Mfg. date" and THEN "Exp. date" next
    to it, so when several keyword+date pairs exist the one after the LAST
    keyword is most likely the expiry and the one before it the mfg date.

    Returns the cleaned first hit, or None if no keyword has a nearby date.
    """
    for keyword_match in reversed(list(keyword_pattern.finditer(raw_text))):
        window_start = keyword_match.end()
        window_text = raw_text[window_start : window_start + SEARCH_WINDOW_SIZE]
        date_match = _STRONG_DATE_PATTERN.search(window_text)
        if date_match:
            return _clean_match(date_match)
        if allow_weak:
            date_match = _WEAK_DATE_PATTERN.search(window_text)
            if date_match:
                return _clean_match(date_match)
    return None


def analyze_expiry(raw_text: str) -> tuple:
    """
    Like find_expiry_text, but ALSO says WHERE the date came from, so the
    caller can decide how much to trust it.

    Returns (source, raw_date_text) where source is one of:
      - "exp_keyword"  -> a date right after an expiry word ("EXP" / "म्याद"),
                          this IS the expiry date.
      - "mfg_keyword"  -> a date right after a manufacturing word
                          ("Mfg"/"Mfd"/"निर्माण"), this is NOT the expiry.
      - "fallback"     -> a strong-looking date found in the bare text,
                          no label next to it (OCR likely dropped it).
      - None           -> nothing date-like was found.
    """
    if not raw_text:
        return (None, None)

    # 1) An explicit expiry keyword is the clearest signal - expiry wins.
    found = _date_near_keyword(raw_text, EXPIRY_KEYWORD_PATTERN)
    if found:
        return ("exp_keyword", found)

    # 2) If the only date is next to a manufacturing keyword, say so - the
    #    caller must NOT show it as the expiry date.
    found = _date_near_keyword(raw_text, MANUFACTURE_KEYWORD_PATTERN, allow_weak=False)
    if found:
        return ("mfg_keyword", found)

    # 3) Whole-text fallback - OCR often keeps the date while losing the
    #    label in front of it (this was the original "empty expiry" bug).
    date_match = _STRONG_DATE_PATTERN.search(raw_text)
    if date_match:
        return ("fallback", _clean_match(date_match))

    return (None, None)


def find_expiry_text(raw_text: str) -> str | None:
    """
    Looks through `raw_text` for an expiry date and returns it as raw text
    (e.g. "12/2026"), or None if nothing date-like was found.

    Returns None when only a MANUFACTURING date was found, because a "made
    on" date must never be presented as an expiry date.
    """
    source, matched = analyze_expiry(raw_text)
    if source == "mfg_keyword":
        return None
    return matched


def is_complete_date(raw_date: str | None) -> bool:
    """
    Returns True only when the date text has a full year at the end (2 or 4
    digits) - i.e. it looks like a real, complete printed date.

    This is a safety guard for a SENSITIVE field: OCR frequently chops the
    final digits off a date (reading "20 JUNE 2029" as "21 JUN.2"), and a
    half-read date is worse than no date at all. Only dates ending in a
    2- or 4-digit year pass:
        "21 JUN 2026"  -> True   "21 JUN 26" -> True
        "12/2026"      -> True   "09/26"     -> True
        "21 JUN.2"     -> False  (year chopped to 1 digit)
        "21 JUN.202"   -> False  (year chopped to 3 digits)
    """
    if not raw_date:
        return False
    last_number = re.findall(r"\d+", raw_date)
    if not last_number:
        return False
    return len(last_number[-1]) in (2, 4)


def format_expiry_in_nepali(raw_date: str | None) -> str | None:
    """
    Turns the raw matched expiry text into a Nepali-friendly display string:
    Devanagari digits and Nepali month names.
      "21 JUN 2026" -> "२१ जुन २०२६"
      "12/2026"     -> "१२/२०२६"
      "DEC 2026"    -> "डिसेम्बर २०२६"

    Returns None when there is nothing to convert. This is for DISPLAY only;
    the raw text is still what is confirmed/corrected by the user.
    """
    if not raw_date:
        return None

    def _month_ne(match: re.Match) -> str:
        month_key = match.group(1).strip(".'\"").lower()
        return _MONTHS_NE.get(month_key[:3], match.group(0))

    text = re.sub(
        rf"(\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*)",
        _month_ne,
        raw_date,
        flags=re.IGNORECASE,
    )
    # OCR often reads "21 JUN.2029" with a stray dot between the month and
    # the year. A punctuation mark glued to a month name is OCR noise, not
    # part of the date - collapse it to a plain space:
    #   "20 JUN.2029" -> "20 जुन 2029" -> "२० जुन २०२९"
    text = re.sub(rf"\s*[./-]+\s*({_DEVANAGARI_MONTHS})", r" \1", text)
    text = re.sub(rf"({_DEVANAGARI_MONTHS})\s*[./-]+\s*", r"\1 ", text)
    # Collapse any resulting double spaces ("DEC  2026" from OCR).
    text = re.sub(r"\s{2,}", " ", text)
    return text.translate(_DIGITS_NE)