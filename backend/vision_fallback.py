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
import logging
import re
import time
from PIL import Image

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from expiry_parser import expiry_is_after_mfg

# Errors from the vision model (rate limits, bad key, outdated model name)
# are reported here so they show up in the server console instead of
# silently turning into "not identified" / "no expiry date".
logger = logging.getLogger("vision")


def _describe_error(error: Exception) -> str:
    text = " ".join(str(error).split())
    return f"{type(error).__name__}: {text[:200]}"


# The exact instructions given to the vision model. Asking for ONLY a JSON
# object (no extra sentences) makes the reply easy and reliable to parse in
# code, instead of us trying to make sense of a free-form paragraph.
PROMPT = (
    "You are looking at a photo of a medicine box or strip, possibly "
    "with Nepali and/or English text on it. "
    "Reply with ONLY a JSON object (no extra words, no markdown) in "
    "exactly this shape: "
    '{"medicine_name": "...", "generic_name": "...", "medicine_name_ne": "...", '
    '"purpose_ne": "...", "mfg_text": "...", "expiry_text": "..."}. '
    "medicine_name is the brand name printed on the package (for example "
    "'Niko'). generic_name is the active ingredient / generic name in "
    "English (for example 'Paracetamol'), usually printed in smaller text "
    "near the brand name - leave it empty if it is not printed. "
    "medicine_name_ne is the brand name written in Nepali (Devanagari). "
    "purpose_ne must be written in Nepali, in one short simple sentence "
    "a non-medical person can understand. "
    "Medicine packaging prints a MANUFACTURING date (labelled 'Mfg.', 'Mfd.' "
    "or 'निर्माण मिति') and a separate, later EXPIRY date (labelled 'Exp.', "
    "'EXP' or 'म्याद'). mfg_text is the manufacturing date exactly as "
    "printed and expiry_text is the expiry date exactly as printed (for "
    "example '20 JUN 2029' or '12/2026'); use an empty string for any date "
    "you cannot find. The expiry date is always later than the "
    "manufacturing date - never mix the two. "
    "If you are not confident what the medicine is, set medicine_name "
    "to an empty string rather than guessing."
)


# A focused prompt asking the vision model ONLY for the two dates. Used
# when OCR read dates but we can't tell the expiry apart from the
# manufacturing date (or couldn't read an expiry date at all). Asking for
# BOTH dates makes the model read the whole date line instead of grabbing
# the first thing that looks like a date, and lets us check that the
# expiry really is the later of the two.
EXPIRY_PROMPT = (
    "You are looking at a photo of a medicine box or strip. "
    "Medicine packaging prints a MANUFACTURING date (labelled 'Mfg.', "
    "'Mfd.' or 'निर्माण मिति') AND a separate EXPIRY date (labelled 'Exp.', "
    "'EXP' or 'म्याद सकिने'), usually one after the other on the same line, "
    "e.g. 'MFG.21 JUN.2026 EXP.20 JUN.2029'. "
    "Reply with ONLY a JSON object (no extra words, no markdown) in exactly "
    "this shape: {\"mfg_text\": \"...\", \"expiry_text\": \"...\"}. "
    "Each value must be that date exactly as printed (for example "
    "'21 JUN 2026' or '12/2026'), or an empty string if you cannot find it. "
    "The expiry date is always LATER than the manufacturing date; read the "
    "digits of each date carefully and never mix the two."
)


# ------------------------------------------------------------------------
# QUOTA: the free Gemini tier allows only a SMALL number of requests per
# DAY for each model (20/day for gemini-3.6-flash as of Oct 2026), plus a
# per-minute limit. Two things follow:
#   1. Never spend a request on anything but a real scan. (The old startup
#      "is the key OK?" check cost one request per server restart - with
#      --reload that was several per coding session.)
#   2. Each model has its OWN daily budget, so when one model reports its
#      day's quota is gone, switch to the next model in the list instead
#      of failing every scan until midnight (Pacific time).
# The list is tried in order; keep the best/fastest model first.
# NOTE: Google renames/retires models regularly - if every scan logs
# "NotFound", update these names from https://ai.google.dev/gemini-api/docs/models
# ------------------------------------------------------------------------
# (gemini-3.8-flash was tried and timed out at 120 s on every call in
# Oct 2026, so it is deliberately not listed.)
VISION_MODEL_NAMES = ["gemini-3.6-flash", "gemini-3.1-flash-lite", "gemini-flash-lite-latest"]

# A single request must not hang a scan forever (some models have been seen
# taking >60 s under load).
REQUEST_TIMEOUT_SECONDS = 60

# When a 429 says the DAILY quota is gone but we can't read the retry delay
# from it, rest that model for this long before trying it again.
DEFAULT_COOLDOWN_SECONDS = 60 * 60


class VisionClient:
    """
    Wraps the Gemini models so the rest of this file can just call
    `client.generate([...])` and not care which model answered, whether one
    of them is out of quota for the day, or how errors are reported.
    """

    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self._models = {name: genai.GenerativeModel(name) for name in VISION_MODEL_NAMES}
        # model name -> unix time until which that model should not be tried
        self._cooldown_until: dict = {}

    def status(self) -> dict:
        """For /health: which models are resting and until when."""
        now = time.time()
        return {
            name: ("resting until %s" % time.strftime("%H:%M", time.localtime(until)))
            if until > now else "available"
            for name, until in ((n, self._cooldown_until.get(n, 0)) for n in VISION_MODEL_NAMES)
        }

    def generate(self, parts: list):
        """
        Sends `parts` (prompt text and/or a PIL image) to the first model
        that is not resting. Returns the response. Raises the last error if
        every model failed, so callers can keep their existing try/except.
        """
        now = time.time()
        last_error: Exception | None = None
        for name in VISION_MODEL_NAMES:
            if self._cooldown_until.get(name, 0) > now:
                continue
            try:
                return self._models[name].generate_content(
                    parts, request_options={"timeout": REQUEST_TIMEOUT_SECONDS}
                )
            except google_exceptions.ResourceExhausted as error:
                last_error = error
                rest_for = _daily_quota_rest_seconds(error)
                if rest_for:
                    self._cooldown_until[name] = now + rest_for
                    logger.warning(
                        "%s: daily free-tier quota used up - resting it for %.1f h and trying the next model",
                        name, rest_for / 3600,
                    )
                else:
                    logger.warning("%s: rate-limited (per-minute) - %s", name, _describe_error(error))
                continue
            except Exception as error:
                last_error = error
                logger.warning("%s: %s - trying the next model", name, _describe_error(error))
                continue
        if last_error is None:
            last_error = RuntimeError("every vision model is resting (daily quota used up)")
        raise last_error


def _daily_quota_rest_seconds(error: Exception) -> float | None:
    """
    Reads a 429 from Gemini. Returns how long to rest the model when the
    DAILY quota is exhausted (from the error's retry_delay, else a default),
    or None when it is only the per-minute limit (worth retrying soon).
    """
    text = str(error)
    if "PerDay" not in text:
        return None
    match = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", text)
    if match:
        return float(match.group(1)) + 60  # a little margin past the reset
    return float(DEFAULT_COOLDOWN_SECONDS)


def try_extract_expiry_date(image: Image.Image, vision_model) -> dict:
    """
    Sends `image` to the vision model and asks it for the manufacturing and
    expiry dates, then keeps the expiry only if it is consistent (later
    than the manufacturing date, when both were read).

    Returns a dict:
      - {"source": "vision", "expiry_text": "21 JUN 2025", "mfg_text": ...}  success
      - {"source": "vision_unavailable", "expiry_text": ""}  no API key
      - {"source": "vision_inconsistent", "expiry_text": ""} expiry not after mfg
      - {"source": "vision_error", "expiry_text": ""}        request failed
    """
    if vision_model is None:
        return {"source": "vision_unavailable", "expiry_text": ""}

    # Try up to twice. The FIRST attempt usually just works; the retry only
    # kicks in when the request SUCCEEDED but the model replied with an
    # empty/unusable/inconsistent answer. We do NOT re-call on exceptions -
    # VisionClient has already tried every available model by then.
    inconsistent = False
    for _attempt in range(2):
        try:
            response = vision_model.generate([EXPIRY_PROMPT, image])
            # The model sometimes wraps JSON in ```json ... ``` even when asked
            # not to - this strips that off before parsing, just in case.
            cleaned = response.text.strip().strip("`").removeprefix("json").strip()
            parsed = json.loads(cleaned)
        except Exception as error:
            # Network error, rate limit, or an unparseable reply - fail
            # gracefully rather than crashing the whole /scan request.
            logger.warning("expiry call failed: %s", _describe_error(error))
            return {"source": "vision_error", "expiry_text": ""}

        expiry_text = parsed.get("expiry_text") or ""
        mfg_text = parsed.get("mfg_text") or ""
        # Sanity check 1: an expiry date always contains digits. Reject
        # clearly unhelpful answers like "unknown" so we don't show garbage.
        if not any(ch.isdigit() for ch in expiry_text):
            continue  # empty / digit-free reply -> try once more
        # Sanity check 2: the expiry must be later than the mfg date. A
        # blurry photo makes the model blend the two ("20 JUN 2026" from
        # "MFG.21 JUN.2026 EXP.20 JUN.2029"); such a blend fails this test.
        if expiry_is_after_mfg(expiry_text, mfg_text) is False:
            logger.warning(
                "expiry %r is not after mfg %r - rejecting (attempt %d)",
                expiry_text, mfg_text, _attempt + 1,
            )
            inconsistent = True
            continue
        return {"source": "vision", "expiry_text": expiry_text, "mfg_text": mfg_text}

    if inconsistent:
        return {"source": "vision_inconsistent", "expiry_text": ""}
    return {"source": "vision_error", "expiry_text": ""}


def create_vision_model(api_key: str | None):
    """
    Sets up the connection to the vision models, using the given API key.

    Returns the ready-to-use VisionClient, or None if no API key was
    given. Returning None (instead of raising an error) is deliberate -
    it lets the rest of the app keep working without Step 3, for anyone
    who hasn't set up a Gemini key yet, rather than forcing it to be
    required from day one.

    Call this ONCE when the server starts (see main.py), not on every
    single request. It makes NO network request - the key is only used
    (and only costs quota) when a photo actually needs the vision model.
    """
    if not api_key or api_key.strip() in ("", "your_gemini_api_key_here"):
        return None
    return VisionClient(api_key.strip())


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
        response = vision_model.generate([PROMPT, image])
        # The model sometimes wraps JSON in ```json ... ``` even when asked
        # not to - this strips that off before parsing, just in case.
        cleaned = response.text.strip().strip("`").removeprefix("json").strip()
        parsed = json.loads(cleaned)
    except Exception as error:
        # Could be a network error, a rate-limit (free tier), or the model
        # replying in a format we couldn't parse. Either way, we fail
        # gracefully rather than crashing the whole /scan request.
        logger.warning("identify call failed: %s", _describe_error(error))
        return {"source": "vision_error", "medicine_name": None, "raw_text": ""}

    expiry_text = parsed.get("expiry_text") or ""
    mfg_text = parsed.get("mfg_text") or ""
    if expiry_is_after_mfg(expiry_text, mfg_text) is False:
        # Same blend problem as in try_extract_expiry_date: don't pass on
        # an expiry that isn't later than the mfg date. main.py will ask
        # the focused date prompt instead.
        logger.warning("identify call: expiry %r not after mfg %r - dropped", expiry_text, mfg_text)
        expiry_text = ""

    return {
        "source": "vision",
        "medicine_name": parsed.get("medicine_name") or None,
        "generic_name": parsed.get("generic_name") or None,
        "medicine_name_ne": parsed.get("medicine_name_ne") or None,
        "purpose_ne": parsed.get("purpose_ne") or None,
        "mfg_text": mfg_text,
        "raw_text": expiry_text,
    }
