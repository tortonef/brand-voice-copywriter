import json

import pytest

from brand_voice.checker import normalize

LANGS = ("en", "it", "fr")


def test_products_cover_both_brands_with_and_without_sustainability(products):
    for prefix in ("ML", "RT"):
        group = [p for sku, p in products.items() if sku.startswith(prefix)]
        assert len(group) >= 6
        assert any(p["sustainability_attrs"] for p in group)
        assert any(not p["sustainability_attrs"] for p in group)


def test_brand_files_are_complete(brands):
    assert set(brands) == {"maison-lumen", "riot-thread"}
    for brand in brands.values():
        assert len(brand["tone"]) == 3
        assert all(brand["banned_words"][lang] for lang in LANGS)
        assert brand["length"]["title_max_chars"] <= 60
        assert brand["length"]["description_sentences"] >= 3
        assert 2 <= len(brand["examples"]) <= 3


def test_lexicon_has_patterns_in_every_language(lexicon):
    for claim in lexicon["claims"]:
        assert set(claim["patterns"]) == set(LANGS), claim["id"]
        assert claim["severity"] in ("fail", "warning")
        for patterns in claim["patterns"].values():
            # Patterns run on normalized text, so accented letters would never match.
            assert all(normalize(p) == p.lower() for p in patterns), claim["id"]


def test_sample_outputs_reference_known_data(cfg, products, brands):
    files = sorted(cfg["paths"]["samples"].glob("*.json"))
    if not files:
        pytest.skip("no sample outputs generated yet")
    for path in files:
        with path.open(encoding="utf-8") as f:
            for d in json.load(f):
                assert d["sku"] in products and d["brand"] in brands and d["lang"] in LANGS
                assert 1 <= len(d["attempts"]) <= 2
