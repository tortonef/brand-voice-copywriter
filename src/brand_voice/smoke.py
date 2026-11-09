"""Smoke check run at the end of setup: data is valid, the checker catches the seeded violations,
and Ollama is reachable (or the app will use demo mode)."""

from __future__ import annotations

from .checker import check, rule_status
from .config import load_config
from .data import load_brands, load_lexicon, load_products, load_seeded
from .llm import unavailable_reason


def main() -> None:
    cfg = load_config()
    paths = cfg["paths"]
    products = load_products(paths["products"], paths["schema"])
    brands = load_brands(paths["brands"])
    lexicon = load_lexicon(paths["claims"])
    errors = []
    for ex in load_seeded(paths["seeded"]):
        findings = check(ex["copy"], products[ex["sku"]], brands[ex["brand"]], ex["lang"], lexicon)
        got = rule_status(findings)
        if got != ex["expect"]:
            errors.append(f"{ex['id']}: expected {ex['expect']}, got {got}")
    if errors:
        raise SystemExit("Smoke check failed:\n" + "\n".join(errors))
    samples = sorted(paths["samples"].glob("*.json"))
    print(
        f"Smoke check OK: {len(products)} products, {len(brands)} brands, "
        f"checker catches the seeded violations, {len(samples)} sample output file(s)."
    )
    reason = unavailable_reason(cfg)
    print(
        "Live generation: ready."
        if reason is None
        else f"Live generation off ({reason}) -> demo mode."
    )


if __name__ == "__main__":
    main()
