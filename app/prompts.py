import json
from pathlib import Path

_GLOSSARY_PATH = Path(__file__).parent / "glossary.json"

TONES = {
    "simple": "simple, friendly, short sentences",
    "premium": "elegant and premium, emphasising craftsmanship and heritage",
    "gift": "warm and gift-oriented, suggesting occasions such as festivals and weddings",
}

LANGS = ("en", "hi", "or")
FACTS = ("product_name", "craft", "material", "dimensions", "maker", "village", "gi")


def load_glossary() -> list[dict]:
    with open(_GLOSSARY_PATH, encoding="utf-8") as f:
        return json.load(f)["terms"]


def terms_for(craft: str) -> list[dict]:
    """Glossary terms relevant to the seller's free-text craft (type name or the term itself)."""
    craft = craft.lower()
    return [t for t in load_glossary()
            if t["craft_type"] in craft or t["term_en"].split("(")[0].strip().lower() in craft]


def glossary_block(craft: str) -> str:
    """Hindi/Odia spellings are given to the model only once a native speaker marked them reviewed."""
    lines = []
    for t in terms_for(craft):
        line = f"- English: {t['term_en']}"
        if t["reviewed"]:
            line += f" | Hindi: {t['term_hi']} | Odia: {t['term_or']}"
        lines.append(line + f" | Meaning: {t['definition']}")
    return "\n".join(lines) or "No glossary terms for this craft."



def build_prompt(facts: dict, tone: str) -> str:
    f = {k: facts.get(k) or "not stated" for k in FACTS}
    return f"""You write accurate product listings for small Odisha craft sellers.
Look at the attached photos of ONE product and write a listing using the supplied facts.

Facts: product_name={f['product_name']}; craft/technique={f['craft']}; material={f['material']}; dimensions={f['dimensions']}; maker={f['maker']}; village={f['village']}; GI={f['gi']}.
Tone: {TONES.get(tone, TONES['simple'])}
Craft terms to keep unchanged (spell exactly as given):
{glossary_block(f['craft'])}

STRICT ACCURACY RULES:
- Treat product_name as the exact identity of the item being sold. Treat craft as the craft, technique, or traditional method used to make it. Never confuse these two fields.
- Use product_name as the main product identity in the title and description. Include craft/technique naturally where relevant, without changing the item into a different product.
- Treat the supplied facts as the source of truth. Do not contradict, replace, or silently omit stated material, dimensions, maker, village, or GI status.
- Include all stated dimensions and materials accurately. You may improve grammar, but never change measurements, units, quantities, or material names.
- Use ONLY information stated in the facts or clearly visible in the photos. Do not infer details from assumptions or cultural stereotypes.
- Never invent claims about purity, quality grades, age, origin, authenticity, certification, GI registration, benefits, durability, or artisan credentials.
- Do not add unsupported promotional claims such as "finest", "premium quality", "authentic", "certified", "timeless heritage", or "masterpiece".
- Tone may change the writing style, but it must NEVER add factual claims. Gift-oriented tone must not invent a recipient, occasion, or suitability claim.
- If a field is "not stated", do not guess it. If facts conflict with the photos or are unclear, avoid the uncertain claim.
- Translate naturally into each language while preserving the same facts and meaning. Do not introduce new claims during translation.
- Title: at most 10 words. Description: 40 to 80 words where possible. Accuracy takes priority over word count.
- Before returning JSON, check each language against the facts. Correct unsupported claims, changed product identity, missing specifications, and inconsistent translations.
- Preserve the specific product name exactly in meaning. Never replace it with a generic craft category, and never invent a product name if it is not stated.
  Do not replace a specific item name with a generic category.
- Never include internal labels, dataset categories, or classification
  metadata such as "open classification" in customer-facing descriptions.
  If such wording appears in a fact, do not reinterpret it; omit it
  unless it is genuinely necessary to identify the product.
- Do not add a location unless it is explicitly provided in the facts
  or clearly supported by the product photos.
- Do not add subjective praise, decorative claims, or suitability statements such as "beautiful addition to your home", "perfect for home decor", or "ideal gift" unless the seller explicitly supplies that claim. Describe the product using verified facts instead.


Return ONLY valid JSON with exactly this shape:
{{
  "en": {{"title": "", "description": ""}},
  "hi": {{"title": "", "description": ""}},
  "or": {{"title": "", "description": ""}}
}}"""
