"""Deterministic compliance checker. Plain Python rules: it never asks the LLM for an opinion."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from langdetect import DetectorFactory, LangDetectException, detect_langs

DetectorFactory.seed = 0  # langdetect is random by default; a fixed seed makes results repeatable

RULES = ("length", "banned_words", "claims", "language")
RULE_LABELS = {
    "length": "Length",
    "banned_words": "Banned words",
    "claims": "Unsupported claims",
    "language": "Language",
}
SEVERITY = {"pass": 0, "warning": 1, "fail": 2}
TITLE_HARD_MAX = 60  # catalog limit, whatever the brand allows
LENGTH_TOLERANCE = (
    0.15  # description up to 15% outside the brand range is a warning, beyond is a fail
)
SHORT_TEXT_WORDS = 15  # below this, language detection is unreliable: mismatch is only a warning


@dataclass
class Finding:
    """One rule outcome. `span` indexes into the field's original text, for highlighting."""

    rule: str
    status: str
    message: str
    field: str | None = None
    span: tuple[int, int] | None = None
    text: str = ""


def normalize(text: str) -> str:
    """Lowercase and strip accents while keeping the length, so match offsets map back to the original."""
    out = []
    for ch in text.replace("’", "'"):
        base = unicodedata.normalize("NFKD", ch)[0]
        out.append(base.lower()[0])
    return "".join(out)


def copy_fields(copy: dict) -> list[tuple[str, str]]:
    """(field name, text) pairs: title, description, bullet 1..n."""
    pairs = [("title", copy.get("title", "")), ("description", copy.get("description", ""))]
    pairs += [(f"bullet {i}", b) for i, b in enumerate(copy.get("bullets", []), 1)]
    return pairs


def _word_regex(patterns: list[str]) -> re.Pattern:
    return re.compile(r"(?<!\w)(?:" + "|".join(patterns) + r")(?!\w)")


def _banned_pattern(word: str) -> str:
    """'luxur*' -> 'luxur\\w*'; everything else is matched literally (accent-insensitive)."""
    word = normalize(word.strip())
    if word.endswith("*"):
        return re.escape(word[:-1]) + r"\w*"
    return re.escape(word)


def _length_status(n: int, lo: int, hi: int) -> str:
    if lo <= n <= hi:
        return "pass"
    if lo * (1 - LENGTH_TOLERANCE) <= n <= hi * (1 + LENGTH_TOLERANCE):
        return "warning"
    return "fail"


def check_length(copy: dict, brand: dict) -> list[Finding]:
    rules = brand["length"]
    out = []
    title = copy.get("title", "")
    title_max = min(rules["title_max_chars"], TITLE_HARD_MAX)
    if not title.strip():
        out.append(Finding("length", "fail", "Title is empty.", "title"))
    elif len(title) > title_max:
        out.append(
            Finding(
                "length",
                "fail",
                f"Title has {len(title)} characters (max {title_max}).",
                "title",
                (title_max, len(title)),
                title[title_max:],
            )
        )
    lo, hi = rules["description_words"]
    n = len(copy.get("description", "").split())
    status = _length_status(n, lo, hi)
    if status != "pass":
        out.append(
            Finding(
                "length",
                status,
                f"Description has {n} words (brand range {lo}-{hi}); "
                f"{'expand' if n < lo else 'shorten'} it to about {(lo + hi) // 2} words.",
                "description",
            )
        )
    bullets = copy.get("bullets", [])
    if len(bullets) != 3:
        out.append(Finding("length", "fail", f"{len(bullets)} bullets (exactly 3 required)."))
    for name, text in copy_fields(copy)[2:]:
        if len(text) > rules["bullet_max_chars"]:
            out.append(
                Finding(
                    "length",
                    "fail",
                    f"Bullet has {len(text)} characters (max {rules['bullet_max_chars']}).",
                    name,
                    (rules["bullet_max_chars"], len(text)),
                    text[rules["bullet_max_chars"] :],
                )
            )
        elif not text.strip():
            out.append(Finding("length", "fail", "Bullet is empty.", name))
    return out


def check_banned(copy: dict, brand: dict, lang: str) -> list[Finding]:
    words = brand["banned_words"].get(lang, [])
    if not words:
        return []
    regex = _word_regex([_banned_pattern(w) for w in words])
    out = []
    for name, text in copy_fields(copy):
        for m in regex.finditer(normalize(text)):
            hit = text[m.start() : m.end()]
            out.append(
                Finding(
                    "banned_words",
                    "fail",
                    f'"{hit}" is banned by {brand["name"]}.',
                    name,
                    m.span(),
                    hit,
                )
            )
    return out


def _values(product: dict, fields: list[str]) -> list[str]:
    return [normalize(v) for f in fields for v in (product.get(f) or [])]


def _supported(evidence: dict | None, match: str, product: dict) -> bool:
    if not evidence:
        return False
    values = _values(product, evidence["fields"])
    terms = evidence["any_of"]
    if terms == ["*"]:
        return bool(values)
    if terms == ["$match"]:
        needle = match.replace(" ", "")
        return any(needle in v.replace(" ", "") for v in values)
    return any(t in v for t in terms for v in values)


def check_claims(copy: dict, product: dict, lang: str, lexicon: dict) -> list[Finding]:
    out = []
    fields = copy_fields(copy)
    normalized = [(name, text, normalize(text)) for name, text in fields]
    for claim in lexicon["claims"]:
        patterns = claim["patterns"].get(lang)
        if not patterns:
            continue
        regex = _word_regex(patterns)
        for name, text, norm in normalized:
            for m in regex.finditer(norm):
                hit = text[m.start() : m.end()]
                if _supported(claim.get("evidence"), m.group(0), product):
                    status = claim.get("if_supported", "pass")
                    msg = f'{claim["label"]} "{hit}" is backed by the product record.'
                    if status != "pass":
                        msg += " " + claim["hint"]
                else:
                    status = claim["severity"]
                    msg = f'{claim["label"]} "{hit}" is not backed by the product record. {claim["hint"]}'
                out.append(Finding("claims", status, msg, name, m.span(), hit))
    materials = " ".join(_values(product, ["materials"]))
    for material, by_lang in lexicon["materials"].items():
        if lang not in by_lang:
            continue
        regex = _word_regex(by_lang[lang])
        for name, text, norm in normalized:
            for m in regex.finditer(norm):
                hit = text[m.start() : m.end()]
                if material in materials:
                    out.append(
                        Finding(
                            "claims",
                            "pass",
                            f'Material "{hit}" is in the product record.',
                            name,
                            m.span(),
                            hit,
                        )
                    )
                else:
                    out.append(
                        Finding(
                            "claims",
                            "fail",
                            f'Material "{hit}" is not in the product materials '
                            f"({', '.join(product.get('materials') or []) or 'none'}).",
                            name,
                            m.span(),
                            hit,
                        )
                    )
    return out


def check_language(copy: dict, lang: str) -> list[Finding]:
    text = " ".join(t for _, t in copy_fields(copy)).strip()
    try:
        top = detect_langs(text)[0]
    except LangDetectException:
        return [Finding("language", "fail", "Could not detect the language (no text?).")]
    if top.lang == lang:
        return []
    status = "warning" if len(text.split()) < SHORT_TEXT_WORDS else "fail"
    return [
        Finding(
            "language", status, f"Text looks like '{top.lang}' ({top.prob:.0%}), expected '{lang}'."
        )
    ]


def check(copy: dict, product: dict, brand: dict, lang: str, lexicon: dict) -> list[Finding]:
    """Run every rule on one text. Rules with no findings passed."""
    return (
        check_length(copy, brand)
        + check_banned(copy, brand, lang)
        + check_claims(copy, product, lang, lexicon)
        + check_language(copy, lang)
    )


def worst(statuses) -> str:
    return max(statuses, key=SEVERITY.__getitem__, default="pass")


def rule_status(findings: list[Finding]) -> dict[str, str]:
    """Worst status per rule; a rule with no findings passed."""
    return {r: worst(f.status for f in findings if f.rule == r) for r in RULES}


def overall(findings: list[Finding]) -> str:
    return worst(f.status for f in findings)


def problems(findings: list[Finding], level: str = "fail") -> list[str]:
    """Human-readable list of findings at `level` or worse; also used as revision feedback."""
    out = []
    for f in findings:
        if SEVERITY[f.status] >= SEVERITY[level]:
            where = f"{f.field}: " if f.field else ""
            out.append(f"{where}{f.message}")
    return out
