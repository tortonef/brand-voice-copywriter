"""The checker is deterministic and is the heart of the repo, so it is tested rule by rule."""

import pytest

from brand_voice.checker import (
    check,
    check_banned,
    check_claims,
    check_language,
    check_length,
    normalize,
    overall,
    problems,
    rule_status,
)


def statuses(findings):
    return [f.status for f in findings]


def with_text(copy, text, field="description"):
    return {**copy, field: text}


# --- normalization -----------------------------------------------------------------------------


def test_normalize_strips_accents_and_case_but_keeps_length():
    text = "Élégante, ÉCO-RESPONSABLE et dell’ambiente"
    norm = normalize(text)
    assert norm == "elegante, eco-responsable et dell'ambiente"
    assert len(norm) == len(text)


# --- length --------------------------------------------------------------------------------------


def test_good_copy_passes_everything(good_copy, products, brands, lexicon):
    findings = check(good_copy, products["ML-0001"], brands["maison-lumen"], "en", lexicon)
    assert overall(findings) == "pass", problems(findings, "warning")


def test_title_over_brand_limit_fails_and_highlights_overflow(good_copy, brands):
    brand = brands["riot-thread"]  # 45 characters
    title = "A" * 50
    [f] = check_length({**good_copy, "title": title, "description": " ".join(["w"] * 50)}, brand)
    assert (f.status, f.field, f.span) == ("fail", "title", (45, 50))


def test_title_hard_limit_is_60_even_if_brand_allows_more(good_copy, brands):
    brand = {
        **brands["maison-lumen"],
        "length": {**brands["maison-lumen"]["length"], "title_max_chars": 80},
    }
    findings = check_length({**good_copy, "title": "x" * 61}, brand)
    assert any(f.field == "title" and f.status == "fail" for f in findings)


def test_empty_title_fails(good_copy, brands):
    assert "fail" in statuses(check_length({**good_copy, "title": "  "}, brands["maison-lumen"]))


@pytest.mark.parametrize(
    ("words", "expected"),
    [(60, []), (90, []), (55, ["warning"]), (100, ["warning"]), (40, ["fail"]), (120, ["fail"])],
)
def test_description_word_range(good_copy, brands, words, expected):
    copy = with_text(good_copy, " ".join(["word"] * words))
    assert statuses(check_length(copy, brands["maison-lumen"])) == expected


def test_short_description_feedback_is_in_sentences(good_copy, brands):
    [f] = check_length(with_text(good_copy, " ".join(["word"] * 48)), brands["maison-lumen"])
    assert "add about 2 full sentences" in f.message


def test_bullet_count_must_be_three(good_copy, brands):
    findings = check_length({**good_copy, "bullets": ["a", "b"]}, brands["maison-lumen"])
    assert statuses(findings) == ["fail"]
    assert "2 bullets" in findings[0].message


def test_long_bullet_fails(good_copy, brands):
    copy = {**good_copy, "bullets": ["x" * 81, "b", "c"]}
    [f] = check_length(copy, brands["maison-lumen"])
    assert (f.status, f.field) == ("fail", "bullet 1")


# --- banned words --------------------------------------------------------------------------------


def test_banned_word_is_case_and_accent_insensitive(good_copy, brands):
    copy = with_text(good_copy, "Une veste ÉLÉGANTE et Intemporelle.")
    findings = check_banned(copy, brands["riot-thread"], "fr")
    assert [f.text for f in findings] == ["ÉLÉGANTE", "Intemporelle"]
    assert statuses(findings) == ["fail", "fail"]


def test_banned_wildcard_matches_word_endings_only(good_copy, brands):
    copy = with_text(good_copy, "Luxurious, a luxury, the ideal deal.")
    hits = [f.text for f in check_banned(copy, brands["maison-lumen"], "en")]
    assert hits == ["Luxurious", "luxury", "deal"]  # "ideal" is not "deal*"


def test_banned_multiword_phrase_and_span(good_copy, brands):
    text = "Un pull bon marche."
    [f] = check_banned(with_text(good_copy, text), brands["maison-lumen"], "fr")
    assert text[f.span[0] : f.span[1]] == "bon marche"


def test_banned_words_are_per_language(good_copy, brands):
    copy = with_text(good_copy, "Un look raffinato.")
    assert check_banned(copy, brands["riot-thread"], "en") == []
    assert check_banned(copy, brands["riot-thread"], "it")


def test_banned_word_spans_point_at_the_original_text(good_copy, brands):
    copy = {**good_copy, "title": "Très élégant"}
    [f] = check_banned(copy, brands["riot-thread"], "fr")
    assert copy["title"][f.span[0] : f.span[1]] == "élégant"


# --- claims --------------------------------------------------------------------------------------


def claim(copy_text, product, lang, lexicon):
    return check_claims(
        {"title": "", "description": copy_text, "bullets": []}, product, lang, lexicon
    )


def test_organic_unsupported_fails(products, lexicon):
    [f] = [
        f
        for f in claim("Organic knit.", products["ML-0001"], "en", lexicon)
        if "Organic" in f.message
    ]
    assert f.status == "fail"


def test_organic_supported_by_materials_passes(products, lexicon):
    findings = claim("Cotone biologico.", products["ML-0004"], "it", lexicon)
    assert statuses(findings) == ["pass", "pass"]  # organic claim + cotton material


def test_generic_eco_fails_without_attrs_and_warns_with_attrs(products, lexicon):
    assert statuses(claim("A sustainable choice.", products["ML-0001"], "en", lexicon)) == ["fail"]
    assert statuses(claim("A sustainable choice.", products["ML-0004"], "en", lexicon)) == [
        "warning"
    ]


@pytest.mark.parametrize(
    ("text", "lang"),
    [
        ("Made in Italy.", "en"),
        ("Realizzato in Italia.", "it"),
        ("Fabriqué en France.", "fr"),
        ("Fatto a mano.", "it"),
        ("Handcrafted collar.", "en"),
        ("Veste imperméable.", "fr"),
        ("Waterproof shell.", "en"),
        ("Carbon-neutral production.", "en"),
    ],
)
def test_claims_with_no_backing_field_always_fail(products, lexicon, text, lang):
    assert "fail" in statuses(claim(text, products["RT-0002"], lang, lexicon))


def test_soft_performance_claim_is_only_a_warning(products, lexicon):
    assert statuses(claim("Breathable for summer.", products["RT-0001"], "en", lexicon)) == [
        "warning"
    ]


def test_percentage_must_appear_in_record(products, lexicon):
    assert "fail" in statuses(claim("100% cashmere.", products["ML-0001"], "en", lexicon))
    product = {**products["ML-0001"], "materials": ["100% cashmere"]}
    assert statuses(claim("100 % cashmere.", product, "en", lexicon)) == ["pass", "pass"]


def test_material_not_in_record_fails(products, lexicon):
    [f] = claim("Soft silk lining.", products["RT-0001"], "en", lexicon)
    assert f.status == "fail" and f.text == "silk"


def test_recycled_supported_passes(products, lexicon):
    findings = claim("Guscio in nylon riciclato.", products["RT-0002"], "it", lexicon)
    assert statuses(findings) == ["pass", "pass"]


def test_italian_pelle_meaning_skin_is_not_leather(products, lexicon):
    assert claim("Morbido sulla pelle.", products["ML-0001"], "it", lexicon) == []


def test_claim_check_only_uses_requested_language(products, lexicon):
    # "durable" is the French word for "sustainable" but just "long-lasting" in English.
    assert claim("A durable knit.", products["ML-0001"], "en", lexicon) == []
    assert statuses(claim("Un tricot durable.", products["ML-0001"], "fr", lexicon)) == ["fail"]


# --- language -------------------------------------------------------------------------------------


def test_language_match_passes(good_copy):
    assert check_language(good_copy, "en") == []


def test_wrong_language_fails(good_copy):
    [f] = check_language(good_copy, "it")
    assert f.status == "fail" and "'en'" in f.message


def test_short_text_mismatch_is_only_a_warning():
    copy = {"title": "Red tee", "description": "A red tee.", "bullets": ["Cotton", "Red", "Loose"]}
    assert statuses(check_language(copy, "fr")) == ["warning"]


def test_language_detection_is_deterministic(good_copy):
    assert all(check_language(good_copy, "en") == [] for _ in range(5))


# --- seeded demo examples and summaries ----------------------------------------------------------


def test_seeded_examples_trigger_expected_rules(seeded, products, brands, lexicon):
    for ex in seeded:
        findings = check(ex["copy"], products[ex["sku"]], brands[ex["brand"]], ex["lang"], lexicon)
        assert rule_status(findings) == ex["expect"], ex["id"]


def test_problems_lists_fails_only_by_default(good_copy, products, brands, lexicon):
    copy = with_text(good_copy, good_copy["description"] + " Breathable and made in Italy.")
    findings = check(copy, products["ML-0001"], brands["maison-lumen"], "en", lexicon)
    fails = problems(findings)
    assert len(fails) == 1 and "made in Italy" in fails[0]
    assert len(problems(findings, "warning")) == 2
