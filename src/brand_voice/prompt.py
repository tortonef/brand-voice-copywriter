"""Build the chat messages: brand guidelines + product facts, with the record as the only source of facts."""

from __future__ import annotations

import json

LANG_NAMES = {"en": "English", "it": "Italian", "fr": "French"}
SEASONS = {"SS": "spring/summer", "AW": "autumn/winter", "all-season": "all seasons"}
FACT_FIELDS = (
    "name",
    "category",
    "gender",
    "colors",
    "materials",
    "pattern",
    "fit",
    "occasions",
    "season",
    "sustainability_attrs",
    "description",
)

# Sent to Ollama as `format`: the model is constrained to this JSON shape.
OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": "string"},
        "bullets": {"type": "array", "items": {"type": "string"}, "minItems": 3, "maxItems": 3},
    },
    "required": ["title", "description", "bullets"],
}


def product_facts(product: dict) -> dict:
    """The facts the model may use. SKU, price, brand and image are left out on purpose."""
    facts = {k: product.get(k) for k in FACT_FIELDS}
    facts["season"] = SEASONS.get(facts["season"], facts["season"])
    return facts


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {i}" for i in items)


def system_prompt(brand: dict, lang: str) -> str:
    language = LANG_NAMES[lang]
    rules = brand["length"]
    title_max = min(rules["title_max_chars"], 60)
    lo, hi = rules["description_words"]
    examples = json.dumps(
        [{k: e[k] for k in ("title", "description", "bullets")} for e in brand["examples"]],
        ensure_ascii=False,
        indent=1,
    )
    return f"""You are a senior copywriter for {brand["name"]}, a fashion brand.

Positioning: {brand["positioning"]}
Audience: {brand["audience"]}
Tone: {", ".join(brand["tone"])}.

Do:
{_bullets(brand["do"])}

Don't:
{_bullets(brand["dont"])}

Preferred vocabulary in {language}: {", ".join(brand["vocabulary"].get(lang, []))}
Never use these words (a * means any ending): {", ".join(brand["banned_words"].get(lang, []))}

Examples of the brand voice. Use them for style only: their facts belong to other products.
{examples}

Rules:
1. Write in {language} only.
2. The PRODUCT record is the ONLY source of facts. Never add facts it does not contain:
   no country of origin, no handmade or artisanal claims, no certifications, no waterproof or other
   technical performance, no percentages, and no materials that are not in "materials".
3. Sustainability: mention only what "sustainability_attrs" lists, in its specific wording.
   If it is empty, say nothing about sustainability, ethics or the environment.
4. title: at most {title_max} characters.
   description: exactly {rules["description_sentences"]} full sentences, at least {lo} and at most {hi} words in total.
   Sentence plan: 1) the look and colour; 2) material and fit; 3) the details in "description";
   the remaining sentences: when and how to wear it (occasions, season) and what to pair it with.
   When you suggest what to pair it with, name garment types and colours, never materials
   (say "wide jeans", not "denim").
   bullets: exactly 3, each at most {rules["bullet_max_chars"]} characters.
Answer with JSON only: {{"title": ..., "description": ..., "bullets": [..., ..., ...]}}."""


def build_messages(product: dict, brand: dict, lang: str) -> list[dict]:
    """Messages for the first attempt."""
    facts = json.dumps(product_facts(product), ensure_ascii=False, indent=1)
    user = f"PRODUCT:\n{facts}\n\nWrite the product copy in {LANG_NAMES[lang]}."
    return [
        {"role": "system", "content": system_prompt(brand, lang)},
        {"role": "user", "content": user},
    ]


def revision_messages(messages: list[dict], previous: dict, issues: list[str]) -> list[dict]:
    """Messages for the single revision pass: the previous answer plus the checker's findings."""
    feedback = (
        "An automatic compliance check found these problems in your copy:\n"
        + _bullets(issues)
        + "\n\nRewrite the copy so that every problem is fixed. Keep what was fine. "
        "Same JSON format, same language."
    )
    return messages + [
        {"role": "assistant", "content": json.dumps(previous, ensure_ascii=False)},
        {"role": "user", "content": feedback},
    ]
