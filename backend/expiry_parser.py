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
#     label while keeping the date itself. When SEVERAL unlabeled dates
#     are found, the LATEST one is returned: packaging prints the
#     manufacturing date first and the expiry date is always later.
#
# OCR NOISE:
# Tesseract routinely confuses characters on foil strips: "MFG" becomes
# "MEG"/"M6G", "0" becomes "O", "1" becomes "l". Before searching, the
# text is normalised with a small, deliberately conservative set of fixes
# (see _normalize_ocr_text). We do NOT fix everything (e.g. "S" -> "5"),
# because a wrong "fix" on a year digit would be worse than no date.
#
# NEPALI DISPLAY:
# format_expiry_in_nepali() turns the raw matched text ("21 JUN 2026",
# "12/2026") into a Nepali-friendly version using Devanagari digits and
# Nepali month names ("२१ जुन २०२६", "१२/२०२६"). The Nepali version is
# meant for DISPLAY only - the raw text is what gets confirmed/corrected.
# ==============================================================================

import re
from datetime import date

# Words that mean "the expiry date is around here" - English and Nepali.
#
# ORDER MATTERS: longer phrases come first, so "expiry date" is matched as
# a whole before the shorter "expiry" or "exp" get a chance to match part
# of it.
#
# "ex[pf]" tolerates the common OCR misread "EXF" for "EXP".
EXPIRY_KEYWORDS = [
    r"expiry\s*date",
    r"exp\.?\s*date",
    r"expiration\s*date",
    r"expires?\s*on",
    r"expiry",
    r"expiration",
    r"ex[pf]\.?",
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

_LATIN_MONTHS_FOR_KEYWORDS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"

# Words that mean "this is the MANUFACTURING (made-on) date" - we must NOT
# present one of these dates as the expiry date.
#
# "m[fe6&]g" tolerates the OCR misreads "MEG" / "M6G" / "M&G" for "MFG",
# which Tesseract produces very often on embossed foil.
MANUFACTURE_KEYWORDS = [
    r"manufacturing\s*date",
    r"manufactured\s*(?:on|date)",
    r"m[fe6&]g\.?\s*date",
    r"m[fe6&]g\.?",
    r"mfd\.?",
    r"production\s*date",
    r"prod\.?\s*date",
    r"निर्माण\s*मिति",
    r"उत्पादन\s*मिति",
    r"बनाइएको\s*मिति",
    r"बनेको\s*मिति",
    # Label RESIDUE: on foil, "MFG.21 JUN" often survives OCR as just
    # "M21 JUN" / "M.21 JUN" - a lone M glued onto a day+month-name date.
    # Nothing else on packaging puts an M directly in front of a date, and
    # "EXP" has no M, so this is safe to treat as a manufacturing label.
    r"(?<![a-z])m[^a-z0-9\s]{0,2}(?=\d{1,2}\s*" + _LATIN_MONTHS_FOR_KEYWORDS + r")",
]

# All the keywords joined into ONE pattern each, so we can find every
# occurrence in a single pass (IGNORECASE handles "EXP", "Exp", "exp").
EXPIRY_KEYWORD_PATTERN = re.compile("|".join(EXPIRY_KEYWORDS), re.IGNORECASE)
MANUFACTURE_KEYWORD_PATTERN = re.compile("|".join(MANUFACTURE_KEYWORDS), re.IGNORECASE)

# Characters allowed BETWEEN the parts of a numeric date: / - or .
# A bare space is NOT accepted for numeric dates ("21 06 2026" is rare on
# packaging, while "10 00" style number runs are common in OCR noise).
_SEP = r"[/\-.]"

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
    rf"\d{{1,2}}(?P<sep>{_SEP})\d{{1,2}}(?P=sep)\d{{2,4}}(?!\d)"  # DD/MM/YYYY, DD/MM/YY (same separator twice)
    rf"|\d{{1,2}}{_SEP}\d{{4}}(?!\d)"                    # MM/YYYY
    rf"|\d{{1,2}}\s*{_MONTHS}[\s.\-/,]*\d{{1,4}}(?!\d)"  # 21 JUN 2026 / 21 JUN.2
    rf"|{_MONTHS}[\s.\-/,]*\d{{2,4}}(?!\d)"               # DEC 2026
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
_MONTH_ORDER = {m: i for i, m in enumerate(_MONTHS_NE, start=1)}

# Regular digits -> Devanagari digits (0-9 -> ०-९), for the Nepali display.
_DIGITS_NE = str.maketrans("0123456789", "०१२३४५६७८९")
# ...and back, so the year/month of a Devanagari date can be compared.
_DIGITS_EN = str.maketrans("०१२३४५६७८९", "0123456789")


# ------------------------------------------------------------------------
# OCR noise clean-up
# ------------------------------------------------------------------------

# Letters that Tesseract prints INSTEAD of a digit when the digit sits next
# to other digits ("2O26" for "2026", "2l" for "21"). Only letters whose
# shape is near-identical to one digit are included - "S"/"5", "B"/"8" and
# "Z"/"2" are deliberately left out because real foil scans showed "2O2S"
# for "2029", so "fixing" S -> 5 would silently produce a wrong year.
_DIGIT_LOOKALIKES = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1"})
_LOOKALIKE_AFTER_DIGIT = re.compile(r"(?<=\d)[OoIl|]")
_LOOKALIKE_BEFORE_DIGIT = re.compile(r"[OoIl|](?=\d)")
_LOOKALIKE_AFTER_MONTH = re.compile(
    rf"({_LATIN_MONTHS}[\s.\-/,]*)([OoIl|])(?=[\dOoIl|])", re.IGNORECASE
)


def _normalize_ocr_text(raw_text: str) -> str:
    """
    Fixes the handful of OCR character confusions that actually break date
    detection, without touching anything else:
      "2O26"      -> "2026"     (letter O inside a number)
      "2l JUN"    -> "21 JUN"   (letter l inside a number)
      "JUN.2O29"  -> "JUN.2029" (letter O starting the year after a month)
    Repeated until stable, so "2OO6" becomes "2006" and not "20O6".
    """
    text = raw_text
    for _ in range(4):
        fixed = _LOOKALIKE_AFTER_DIGIT.sub(lambda m: m.group(0).translate(_DIGIT_LOOKALIKES), text)
        fixed = _LOOKALIKE_BEFORE_DIGIT.sub(lambda m: m.group(0).translate(_DIGIT_LOOKALIKES), fixed)
        fixed = _LOOKALIKE_AFTER_MONTH.sub(
            lambda m: m.group(1) + m.group(2).translate(_DIGIT_LOOKALIKES), fixed
        )
        if fixed == text:
            break
        text = fixed
    return text


# Year window a printed expiry/manufacturing date can realistically fall in.
# Medicines are rarely on a shelf more than ~10 years after manufacture or
# with more than ~10 years of shelf life. A second window covers Nepali
# (Bikram Sambat) years, which run about 57 years ahead of the Gregorian
# calendar (2026 AD = 2082/2083 BS).
def _year_windows() -> tuple:
    this_year = date.today().year
    return ((this_year - 12, this_year + 15), (this_year + 45, this_year + 75))


def is_plausible_date(raw_date: str | None) -> bool:
    """
    Rejects number runs that merely LOOK like a date shape but cannot be a
    real printed date - OCR noise like "0.21 1014" or "10.00" (a price):
      - the year must fall in a realistic window (see _year_windows),
      - a numeric month must be 1-12 (either order for DD/MM vs MM/DD),
      - a numeric day must be 1-31.
    Chopped years ("21 JUN.2") are NOT rejected here - is_complete_date()
    handles those separately, so callers can still tell "incomplete" apart
    from "garbage".
    """
    if not raw_date:
        return False
    text = raw_date.translate(_DIGITS_EN)
    numbers = re.findall(r"\d+", text)
    if not numbers:
        return False

    year_text = numbers[-1]
    if len(year_text) in (2, 4):
        year = int(year_text) + (2000 if len(year_text) == 2 else 0)
        if not any(lo <= year <= hi for lo, hi in _year_windows()):
            return False

    has_month_name = re.search(_MONTHS, text, re.IGNORECASE) is not None
    if has_month_name:
        if len(numbers) >= 2:
            day = int(numbers[0])
            if not 1 <= day <= 31:
                return False
        return True

    parts = [int(n) for n in numbers[:-1]]
    if len(parts) == 1:  # MM/YYYY
        return 1 <= parts[0] <= 12
    if len(parts) == 2:  # DD/MM/YYYY (or MM/DD/YYYY)
        a, b = parts
        return (1 <= a <= 31 and 1 <= b <= 12) or (1 <= a <= 12 and 1 <= b <= 31)
    return False


def _plausible_matches(pattern: re.Pattern, text: str) -> list:
    """Every cleaned match of `pattern` in `text` that passes is_plausible_date."""
    found = []
    for match in pattern.finditer(text):
        cleaned = _clean_match(match)
        if cleaned and is_plausible_date(cleaned):
            found.append(cleaned)
    return found


def _clean_match(match: re.Match) -> str:
    # strip() removes stray separators OCR sometimes leaves on the end,
    # e.g. "12/2026." -> "12/2026"
    return match.group(0).strip(" .-/,:)(")


def _date_near_keyword(
    raw_text: str, keyword_pattern: re.Pattern, allow_weak: bool = True
) -> str | None:
    """
    Searches for a date in the text right after each occurrence of the
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
        strong = _plausible_matches(_STRONG_DATE_PATTERN, window_text)
        if strong:
            return strong[0]
        if allow_weak:
            weak = _plausible_matches(_WEAK_DATE_PATTERN, window_text)
            if weak:
                return weak[0]
    return None


def _date_sort_key(raw_date: str) -> tuple:
    """
    Turns a raw date like "21 JUN 2026" / "12/2029" / "२० जुन २०२९" into a
    (year, month) tuple so two dates can be compared chronologically.
    Unknown parts become 0, so an unparseable date sorts first (= least
    likely to be chosen as "the latest").
    """
    text = raw_date.translate(_DIGITS_EN)
    numbers = re.findall(r"\d+", text)
    if not numbers:
        return (0, 0)
    year = int(numbers[-1])
    if len(numbers[-1]) == 2:
        year += 2000
    elif len(numbers[-1]) != 4:
        year = 0  # chopped year, e.g. "JUN.2" - don't trust it
    month = 0
    month_match = re.search(_LATIN_MONTHS, text, re.IGNORECASE)
    if month_match:
        month = _MONTH_ORDER.get(month_match.group(0)[:3].lower(), 0)
    elif len(numbers) >= 2:
        # "DD/MM/YYYY" -> second-to-last number; "MM/YYYY" -> first number
        try:
            month = int(numbers[-2])
        except ValueError:
            month = 0
    return (year, month)


def _latest_unlabeled_date(raw_text: str) -> str | None:
    """
    Whole-text fallback: finds every strong-looking date and returns the
    LATEST one. Packaging prints the manufacturing date before the expiry
    date, and the expiry is always chronologically later - so when OCR
    dropped both labels, picking the latest date is the safe choice (the
    old behaviour of picking the FIRST date returned the mfg date).
    """
    candidates = _plausible_matches(_STRONG_DATE_PATTERN, raw_text)
    if not candidates:
        return None
    complete = [c for c in candidates if is_complete_date(c)]
    pool = complete or candidates
    # max() keeps the FIRST maximum on ties, so equal dates don't reorder.
    return max(pool, key=_date_sort_key)


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

    text = _normalize_ocr_text(raw_text)

    # 1) An explicit expiry keyword is the clearest signal - expiry wins.
    found = _date_near_keyword(text, EXPIRY_KEYWORD_PATTERN)
    if found:
        return ("exp_keyword", found)

    # 2) If the only date is next to a manufacturing keyword, say so - the
    #    caller must NOT show it as the expiry date. BUT if there is ALSO a
    #    later, unlabeled date in the text, that later date is almost
    #    certainly the expiry whose "EXP" label OCR dropped - e.g.
    #    "MFG.21 JUN.2026 ???.20 JUN.2029".
    mfg_date = _date_near_keyword(text, MANUFACTURE_KEYWORD_PATTERN, allow_weak=False)
    latest = _latest_unlabeled_date(text)
    if mfg_date:
        if (
            latest
            and latest != mfg_date
            and is_complete_date(latest)
            and _date_sort_key(latest) > _date_sort_key(mfg_date)
        ):
            return ("fallback", latest)
        return ("mfg_keyword", mfg_date)

    # 3) Whole-text fallback - OCR often keeps the date while losing the
    #    label in front of it (this was the original "empty expiry" bug).
    if latest:
        return ("fallback", latest)

    return (None, None)


# How much we trust each kind of result, used to pick the best of several
# OCR passes (see analyze_expiry_texts). Complete dates always beat chopped
# ones; an explicit EXP label beats an unlabeled date.
_SOURCE_RANK = {"exp_keyword": 3, "fallback": 2, "mfg_keyword": 1, None: 0}


def expiry_confidence(source: str | None, raw_date: str | None) -> int:
    """Higher is better. 0 means "nothing usable"."""
    if source is None or not raw_date:
        return 0
    return _SOURCE_RANK.get(source, 0) * 2 + (1 if is_complete_date(raw_date) else 0)


def analyze_expiry_texts(texts: list) -> tuple:
    """
    Runs analyze_expiry over SEVERAL text blocks (e.g. the output of
    several OCR passes - different rotations, a zoomed-in crop of the date
    line...) and returns the single most trustworthy (source, date).
    """
    results = [analyze_expiry(text) for text in texts]

    # Cross-check between passes: if ANY pass saw a date next to a
    # manufacturing label, then an UNLABELED date from another pass that is
    # not chronologically later than it cannot be the expiry - it is the
    # same mfg date read by a pass that lost the "MFG" label. Without this,
    # "MFG,21 JUN 2026" from one pass and a bare "21 JUN 2026" from another
    # would let the bare one win and be shown as the expiry date.
    mfg_keys = [
        _date_sort_key(found)
        for source, found in results
        if source == "mfg_keyword" and found and is_complete_date(found)
    ]
    latest_mfg = max(mfg_keys) if mfg_keys else None

    best = (None, None)
    best_score = 0
    for source, found in results:
        if (
            source == "fallback"
            and latest_mfg is not None
            and _date_sort_key(found) <= latest_mfg
        ):
            source = "mfg_keyword"
        score = expiry_confidence(source, found)
        if score > best_score:
            best, best_score = (source, found), score
    return best


def expiry_is_after_mfg(expiry_text: str | None, mfg_text: str | None) -> bool | None:
    """
    Sanity check for a pair of dates read off one package: the expiry must
    be LATER than the manufacturing date. Returns True/False when both
    dates are complete enough to compare (year known), None when they are
    not (so the caller can't draw a conclusion either way).

    Why: a vision model reading a blurry photo sometimes blends the two
    printed dates ("MFG.21 JUN.2026 EXP.20 JUN.2029" -> "20 JUN 2026").
    Such a blend is never later than the mfg date, so this catches it.
    """
    if not expiry_text or not mfg_text:
        return None
    exp_key = _date_sort_key(_normalize_ocr_text(expiry_text))
    mfg_key = _date_sort_key(_normalize_ocr_text(mfg_text))
    if exp_key[0] == 0 or mfg_key[0] == 0:
        return None
    return exp_key > mfg_key


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


def strip_expiry_label(text: str | None) -> str | None:
    """
    Removes a label the vision model sometimes copies along with the date,
    so "EXP.20 JUN.2029" / "Expiry: 12/2026" become "20 JUN.2029" /
    "12/2026". If no date can be isolated the text is returned unchanged,
    just trimmed - never None for a non-empty input.
    """
    if not text:
        return None
    source, found = analyze_expiry(text)
    if source in ("exp_keyword", "fallback") and found:
        return found
    return text.strip(" .-/,:")


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
    text = re.sub(rf"\s*[./,-]+\s*({_DEVANAGARI_MONTHS})", r" \1", text)
    text = re.sub(rf"({_DEVANAGARI_MONTHS})\s*[./,-]+\s*", r"\1 ", text)
    # Collapse any resulting double spaces ("DEC  2026" from OCR).
    text = re.sub(r"\s{2,}", " ", text)
    return text.translate(_DIGITS_NE)
