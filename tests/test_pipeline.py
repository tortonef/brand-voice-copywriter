import csv
import io
import json

from brand_voice.evaluate import report
from brand_voice.export import to_csv, to_json
from brand_voice.pipeline import from_dict, generate, to_dict


def fake_chat(answers):
    calls = []

    def chat(messages, cfg):
        calls.append(messages)
        return answers[len(calls) - 1]

    return chat, calls


def test_compliant_first_attempt_is_not_revised(good_copy, products, brands, lexicon, cfg):
    chat, calls = fake_chat([good_copy])
    r = generate(
        products["ML-0001"], "maison-lumen", brands["maison-lumen"], "en", lexicon, cfg, chat
    )
    assert len(calls) == 1 and not r.revised and r.final.status == "pass"


def test_failing_attempt_gets_one_revision_with_feedback(good_copy, products, brands, lexicon, cfg):
    bad = {**good_copy, "title": "Luxury Cashmere, Made in Italy"}
    chat, calls = fake_chat([bad, good_copy])
    r = generate(
        products["ML-0001"], "maison-lumen", brands["maison-lumen"], "en", lexicon, cfg, chat
    )
    assert r.revised and [a.status for a in r.attempts] == ["fail", "pass"]
    feedback = calls[1][-1]["content"]
    assert '"Luxury"' in feedback and "Made in Italy" in feedback


def test_only_one_revision_even_if_still_failing(good_copy, products, brands, lexicon, cfg):
    bad = {**good_copy, "title": "Luxury Cashmere"}
    chat, calls = fake_chat([bad, bad, bad])
    r = generate(
        products["ML-0001"], "maison-lumen", brands["maison-lumen"], "en", lexicon, cfg, chat
    )
    assert len(calls) == 2 and r.final.status == "fail"


def test_roundtrip_reruns_checker(good_copy, products, brands, lexicon, cfg):
    chat, _ = fake_chat([{**good_copy, "title": "Luxury Cashmere"}, good_copy])
    r = generate(
        products["ML-0001"], "maison-lumen", brands["maison-lumen"], "en", lexicon, cfg, chat
    )
    d = json.loads(json.dumps(to_dict(r)))
    assert "findings" not in d["attempts"][0]
    again = from_dict(d, products, brands, lexicon)
    assert [a.status for a in again.attempts] == ["fail", "pass"]


def test_exports_and_report(good_copy, products, brands, lexicon, cfg):
    chat, _ = fake_chat([{**good_copy, "title": "Luxury Cashmere"}, good_copy, good_copy])
    r1 = generate(
        products["ML-0001"], "maison-lumen", brands["maison-lumen"], "en", lexicon, cfg, chat
    )
    r2 = generate(
        products["ML-0001"], "maison-lumen", brands["maison-lumen"], "en", lexicon, cfg, chat
    )
    rows = list(csv.DictReader(io.StringIO(to_csv([r1, r2], products).decode("utf-8-sig"))))
    assert rows[0]["status"] == "pass" and rows[0]["revised"] == "True"
    assert rows[0]["rule_banned_words"] == "pass" and rows[0]["bullet_3"] == "Ribbed cuffs and hem"
    data = json.loads(to_json([r1]))
    assert data[0]["attempts"][0]["rules"]["banned_words"] == "fail"
    md = report([r1, r2], brands, products, "fake-model")
    assert "| Compliant on the first attempt | 1/2 (50%) |" in md
    assert "| Compliant after one automatic revision | 2/2 (100%) |" in md
