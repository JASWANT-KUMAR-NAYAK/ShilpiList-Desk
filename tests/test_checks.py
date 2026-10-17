from app import checks, prompts
from app.prompts import build_prompt



def test_unsupported_flags_claims_not_supported_by_facts():
    content = {
        "en": {
            "title": "Authentic silver box",
            "description": "A pure silver box, 925 grade, 12 flowers."
        },
        "hi": {"title": "", "description": ""},
        "or": {"title": "", "description": ""},
    }

    warnings = checks.unsupported(content, "filigree silver 5 cm")

    assert any("authenticity" in w.lower() for w in warnings)
    assert any("purity" in w.lower() for w in warnings)
    assert any("925" in w for w in warnings)
    assert any("12" in w for w in warnings)


def test_negative_gi_statement_does_not_trigger_gi_warning():
    content = listing("This product is not GI certified.")

    warnings = checks.unsupported(content, "cotton pouch 10 x 15 cm not certified")

    assert not any("GI status" in w for w in warnings)


def test_odia_numbers_match_ascii_numbers_in_facts():
    content = listing("Dimensions are ୧୨ × ୧୮ inches.")

    warnings = checks.unsupported(content, "wood 12 x 18 inches")

    assert not any("number" in w.lower() for w in warnings)


def listing(text):
    return {k: {"title": "", "description": text} for k in ("en", "hi", "or")}


def test_missing_terms_flags_absent_english_term_case_insensitively():
    assert checks.missing_terms(listing("A silver box"), "silver filigree") == ["en: Tarakasi"]
    assert checks.missing_terms(listing("Fine TARAKASI work"), "silver filigree") == []


def test_missing_terms_matches_the_sellers_own_word_and_ignores_other_crafts():
    assert checks.missing_terms(listing("A silver box"), "Tarakasi") == ["en: Tarakasi"]
    assert checks.missing_terms(listing("A mug"), "ceramic") == []


def reviewed_glossary(monkeypatch):
    original = prompts.load_glossary
    monkeypatch.setattr(prompts, "load_glossary", lambda: [{**t, "reviewed": True} for t in original()])


def test_hindi_and_odia_terms_are_checked_only_when_reviewed(monkeypatch):
    assert checks.missing_terms(listing("Dhokra"), "dhokra") == []
    reviewed_glossary(monkeypatch)
    assert checks.missing_terms(listing("Dhokra"), "dhokra") == ["hi: ढोकरा", "or: ଢୋକରା"]


def test_prompt_gives_hindi_and_odia_spellings_only_when_reviewed(monkeypatch):
    facts = {"craft": "dhokra", "material": "brass", "dimensions": "8 cm"}
    assert "ढोकरा" not in build_prompt(facts, "simple")
    reviewed_glossary(monkeypatch)
    assert "ढोकरा" in build_prompt(facts, "simple") and "ଢୋକରା" in build_prompt(facts, "simple")


def test_prompt_forbids_invention_and_marks_missing_facts():
    p = build_prompt({"craft": "mug", "material": "clay", "dimensions": "8 cm"}, "premium")
    assert "maker=not stated; village=not stated; GI=not stated" in p
    assert "Never invent" in p and "elegant and premium" in p
