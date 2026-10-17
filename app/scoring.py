"""Cheap, objective checks used by the Day-1 script and the evaluation run.

These do NOT replace a native-speaker review; they catch the obvious failures
(wrong script, language drift, missing craft terms) automatically.
"""
from .prompts import terms_for

# Unicode blocks: Odia U+0B00-0B7F, Devanagari U+0900-097F
_RANGES = {"or": (0x0B00, 0x0B7F), "hi": (0x0900, 0x097F)}


def script_share(text: str, lang: str) -> float:
    """Share of letters in `text` that belong to the expected script.

    For English, the share of ASCII letters. Returns 0.0 for text with no letters.
    """
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    if lang == "en":
        return sum(ch.isascii() for ch in letters) / len(letters)
    lo, hi = _RANGES[lang]
    return sum(lo <= ord(ch) <= hi for ch in letters) / len(letters)


def term_hit(text: str, craft: str, lang: str) -> bool:
    """True if any approved glossary term for this craft appears in `text`."""
    key = {"en": "term_en", "hi": "term_hi", "or": "term_or"}[lang]
    for t in terms_for(craft):
        term = t[key]
        if not term:
            continue
        # term_en like "Tarakasi (silver filigree)": match the leading name too
        names = {term, term.split("(")[0].strip()}
        if any(n and n.lower() in text.lower() for n in names):
            return True
    return False


def score_listing(content: dict, craft: str) -> dict:
    out = {}
    for lang in ("en", "hi", "or"):
        text = f"{content[lang]['title']} {content[lang]['description']}"
        out[f"{lang}_script_share"] = round(script_share(text, lang), 3)
        out[f"{lang}_term_hit"] = term_hit(text, craft, lang)
        out[f"{lang}_desc_words"] = len(content[lang]["description"].split())
    return out
