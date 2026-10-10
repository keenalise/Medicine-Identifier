# ==============================================================================
# test_expiry_parser.py
#
# Regression tests for expiry_parser.py, built from text that Tesseract
# ACTUALLY produced on real medicine strips (see the sample photo in the
# repo root). Run with either:
#     python test_expiry_parser.py
#     pytest test_expiry_parser.py
# ==============================================================================

from expiry_parser import (
    analyze_expiry,
    analyze_expiry_texts,
    expiry_is_after_mfg,
    find_expiry_text,
    format_expiry_in_nepali,
    is_complete_date,
    is_plausible_date,
    strip_expiry_label,
)

CASES = {
    # clean print: both labels present
    "B.No NKT 26580 MFG.21 JUN.2026 EXP.20 JUN.2029": ("exp_keyword", "20 JUN.2029"),
    "Mfg 12/2024 Exp 12/2026": ("exp_keyword", "12/2026"),
    "MFG 09/24 EXP 09/26": ("exp_keyword", "09/26"),
    "Expiry Date : 31-12-2027": ("exp_keyword", "31-12-2027"),
    "म्याद सकिने मिति: २० जुन २०२९": ("exp_keyword", "२० जुन २०२९"),
    "Manufactured by: National Healthcare Pvt. Ltd. MFG.21 JUN.2026 EXP.20 JUN.2029": (
        "exp_keyword", "20 JUN.2029"),
    # OCR misreads of the labels / digits
    "NKT 26580 MEG 21 JUN.2": ("mfg_keyword", "21 JUN.2"),          # MEG = MFG, year chopped
    "EXP.2O JUN.2O29": ("exp_keyword", "20 JUN.2029"),             # letter O for zero
    "EXF 2l/12/2O27": ("exp_keyword", "21/12/2027"),               # EXF for EXP, l for 1
    "26580 M6G.21 JUN 2026": ("mfg_keyword", "21 JUN 2026"),       # M6G = MFG
    "NKT 26580 M21 JUN. 2026-00 >)": ("mfg_keyword", "21 JUN. 2026"),  # only the M of MFG survived
    "NKT 26580 M21 JUN. 2026 EXP 20 JUN 2029": ("exp_keyword", "20 JUN 2029"),
    "NKT 26580 M21 JUN. 2026 20 JUN 2029": ("fallback", "20 JUN 2029"),
    "Ibuprofen 400 mg 10 JAN 2027": ("fallback", "10 JAN 2027"),    # no M residue -> still a date
    # labels lost entirely: the LATER date is the expiry
    "NKT 26580 MEG 21 JUN.2026 20 JUN.2029": ("fallback", "20 JUN.2029"),
    "21 JUN 2026   20 JUN 2029": ("fallback", "20 JUN 2029"),
    "20 JUN 2029   21 JUN 2026": ("fallback", "20 JUN 2029"),
    # only a manufacturing date -> must NOT be offered as the expiry
    "Mfg. 21 JUN 2026": ("mfg_keyword", "21 JUN 2026"),
    # noise that must NOT become a date
    "M.R.P.Rs.10.00 PER 10 TABS": (None, None),
    "Mfg. Lic. No.: 1154": (None, None),
    "EXP 2O29 ...": (None, None),
    "2058010:0.21 1014.2026050000 110 0000 1110": (None, None),      # digit soup from a foil band
    "0010? 2000 011 10 00/24-0707 1901": (None, None),
    "": (None, None),
}


def test_analyze_expiry():
    for text, expected in CASES.items():
        assert analyze_expiry(text) == expected, (text, analyze_expiry(text), expected)


def test_find_expiry_text_hides_mfg_only():
    assert find_expiry_text("Mfg. 21 JUN 2026") is None
    assert find_expiry_text("Exp. 21 JUN 2026") == "21 JUN 2026"


def test_best_of_many_passes():
    passes = ["MEG 21 JUN.2", "garbage", "MFG.21 JUN.2026 EXP.20 JUN.2029"]
    assert analyze_expiry_texts(passes) == ("exp_keyword", "20 JUN.2029")
    assert analyze_expiry_texts(["nothing here", ""]) == (None, None)
    # One pass kept the MFG label, another lost it: the bare date is the
    # SAME manufacturing date and must not be promoted to "expiry".
    passes = ["MFG,21 JUN. 2026) =) |", "NKT 26580 M21 JUN. 2026-00 >)"]
    assert analyze_expiry_texts(passes) == ("mfg_keyword", "21 JUN. 2026")
    # ...but a bare date that is LATER than the labelled mfg date is the expiry.
    passes = ["MFG,21 JUN. 2026", "NKT 26580 M21 JUN. 2026 20 JUN 2029"]
    assert analyze_expiry_texts(passes) == ("fallback", "20 JUN 2029")


def test_complete_and_plausible():
    assert is_complete_date("21 JUN 2026") and is_complete_date("09/26")
    assert not is_complete_date("21 JUN.2") and not is_complete_date("21 JUN.202")
    assert is_plausible_date("12/2026") and is_plausible_date("20 JUN.2029")
    assert is_plausible_date("असार 2082")                 # Bikram Sambat year
    assert not is_plausible_date("13/2026")               # month 13
    assert not is_plausible_date("0.21 1014")             # year 1014
    assert not is_plausible_date("10.00")                 # price


def test_strip_label_and_nepali_display():
    assert strip_expiry_label("EXP.20 JUN.2029") == "20 JUN.2029"
    assert strip_expiry_label("Expiry: 12/2026") == "12/2026"
    assert strip_expiry_label("20 JUN 2029") == "20 JUN 2029"
    assert strip_expiry_label(None) is None
    assert format_expiry_in_nepali("20 JUN.2029") == "२० जुन २०२९"
    assert format_expiry_in_nepali("12/2026") == "१२/२०२६"
    assert format_expiry_in_nepali(None) is None


def test_expiry_is_after_mfg():
    assert expiry_is_after_mfg("20 JUN 2029", "21 JUN 2026") is True
    assert expiry_is_after_mfg("20 JUN.2029", "MFG.21 JUN.2026") is True
    assert expiry_is_after_mfg("12/2026", "09/2024") is True
    # the blurry-photo blend: day from EXP, year from MFG -> not later
    assert expiry_is_after_mfg("20 JUN 2026", "21 JUN 2026") is False
    assert expiry_is_after_mfg("05/2024", "09/2024") is False
    # unknown when either side is missing or has no usable year
    assert expiry_is_after_mfg("20 JUN 2029", "") is None
    assert expiry_is_after_mfg(None, "21 JUN 2026") is None
    assert expiry_is_after_mfg("20 JUN.2", "21 JUN 2026") is None


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok ", name)
    print("all tests passed")
