
"""Advisory checks for obvious listing risks.

These checks are heuristic only. They do not verify factual accuracy.
Odia text still requires native-speaker review.
"""
import re

from .prompts import terms_for

# Phrases that may indicate claims requiring seller verification.
CLAIM_PATTERNS = {
    "authenticity": [
        r"\bauthentic\b", r"\bgenuine\b",
        r"\bप्रामाणिक\b", r"\bअसली\b",
        r"\bପ୍ରାମାଣିକ\b", r"\bଅସଲି\b",
    ],
    "certification": [
        r"\bcertified\b", r"\bcertification\b",
        r"\bप्रमाणित\b", r"\bप्रमाणीकरण\b",
        r"\bପ୍ରମାଣିତ\b",
    ],
    "purity": [
        r"\bpure\b", r"\bsterling\b",
        r"\bशुद्ध\b", r"\bखरा\b",
        r"\bଶୁଦ୍ଧ\b",
    ],
    "age": [
        r"\bantique\b", r"\bvintage\b",
        r"\bप्राचीन\b", r"\bपुराना\b",
        r"\bପ୍ରାଚୀନ\b", r"\bପୁରୁଣା\b",
    ],
    "GI status": [
        r"\bgi[\s-]*tag(?:ged)?\b",
        r"\bgi[\s-]*certified\b",
        r"\bgi[\s-]*registered\b",
        r"\bजीआई\b.{0,20}\b(टैग|प्रमाणित|पंजीकृत)\b",
        r"\bଜିଆଇ\b.{0,20}\b(ଟ୍ୟାଗ|ପ୍ରମାଣିତ|ପଞ୍ଜୀକୃତ)\b",
    ],
}


def unsupported(content: dict, facts: str) -> list[str]:
    """Flag claim language and numbers for seller review across all languages."""
    fact_text = facts.lower()
    all_text = " ".join(
        f"{content.get(lang, {}).get('title', '')} "
        f"{content.get(lang, {}).get('description', '')}"
        for lang in ("en", "hi", "or")
    ).lower()

    warnings = []

    for label, patterns in CLAIM_PATTERNS.items():
        if label == "GI status":
            negative_gi = re.search(
                r"\b(?:not|no|isn't|is not)\s+(?:gi[\s-]*)?"
                r"(?:certified|registered|tagged)\b",
                all_text,
                re.IGNORECASE,
            )
            if negative_gi:
                continue

        if any(re.search(pattern, all_text, re.IGNORECASE) for pattern in patterns):
            if not any(
                re.search(pattern, fact_text, re.IGNORECASE)
                for pattern in patterns
            ):
                warnings.append(
                    f"Review {label} claim: confirm it is explicitly supported by the supplied facts."
                )

        # Normalize Hindi and Odia digits to ASCII before comparing.
    digit_translation = str.maketrans(
        "०१२३४५६७८९୦୧୨୩୪୫୬୭୮୯",
        "01234567890123456789"
    )

    fact_text = fact_text.translate(digit_translation)
    all_text = all_text.translate(digit_translation)

    given_numbers = set(re.findall(r"\d+(?:\.\d+)?", fact_text))
    output_numbers = set(re.findall(r"\d+(?:\.\d+)?", all_text))

    for number in sorted(output_numbers - given_numbers):
        warnings.append(
            f"Review number '{number}': confirm it matches the supplied product facts."
        )
    for number in sorted(output_numbers - given_numbers):
        warnings.append(
            f"Review number '{number}': confirm it matches the supplied product facts."
        )

    return warnings


def missing_terms(content: dict, craft: str) -> list[str]:
    """Flag approved glossary terms missing from relevant language text."""
    out = []
    for term_data in terms_for(craft):
        for lang, key in (
            ("en", "term_en"),
            ("hi", "term_hi"),
            ("or", "term_or"),
        ):
            term = (term_data.get(key) or "").split("(")[0].strip()
            text = (
                f"{content.get(lang, {}).get('title', '')} "
                f"{content.get(lang, {}).get('description', '')}"
            ).lower()

            if term and (lang == "en" or term_data.get("reviewed")):
                if term.lower() not in text:
                    out.append(f"{lang}: {term}")

    return out
