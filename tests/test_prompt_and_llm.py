import io
import json
import urllib.error

import pytest

from brand_voice import llm
from brand_voice.llm import LLMError, parse_copy, unavailable_reason
from brand_voice.prompt import build_messages, product_facts, revision_messages


def test_facts_leave_out_sku_price_brand_image(products):
    facts = product_facts(products["ML-0003"])
    assert not {"sku", "price_eur", "brand", "image"} & facts.keys()
    assert facts["season"] == "autumn/winter"
    assert facts["sustainability_attrs"] == ["responsibly sourced wool (RWS certified)"]


def test_prompt_contains_brand_rules_and_language(products, brands):
    system, user = build_messages(products["RT-0001"], brands["riot-thread"], "fr")
    assert system["role"] == "system" and user["role"] == "user"
    assert "Riot Thread" in system["content"]
    assert "Write in French only" in system["content"]
    assert "élégan*" in system["content"]  # French banned words
    assert "at most 45 characters" in system["content"]
    assert "at least 40 and at most 70 words" in system["content"]
    assert "ONLY source of facts" in system["content"]
    assert '"Glitch Graphic Tee"' in user["content"]


def test_revision_appends_previous_answer_and_feedback(products, brands):
    first = build_messages(products["RT-0001"], brands["riot-thread"], "en")
    previous = {"title": "t", "description": "d", "bullets": ["a", "b", "c"]}
    msgs = revision_messages(first, previous, ['title: "elegant" is banned'])
    assert msgs[:2] == first
    assert json.loads(msgs[2]["content"]) == previous and msgs[2]["role"] == "assistant"
    assert '"elegant" is banned' in msgs[3]["content"]


def test_parse_copy_valid_and_cleans_whitespace():
    out = parse_copy('{"title": " T ", "description": "a\\n b", "bullets": [" x", "y", "z"]}')
    assert out == {"title": "T", "description": "a b", "bullets": ["x", "y", "z"]}


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[1, 2]",
        '{"title": "t", "bullets": []}',
        '{"title": "t", "description": "d", "bullets": "x"}',
    ],
)
def test_parse_copy_rejects_bad_output_with_clear_error(text):
    with pytest.raises(LLMError, match="Model output"):
        parse_copy(text)


def test_chat_sends_think_false_and_json_schema(monkeypatch, cfg):
    sent = {}

    def fake_request(url, body, timeout):
        sent.update(url=url, body=body)
        return {
            "message": {"content": '{"title": "T", "description": "D", "bullets": ["a","b","c"]}'}
        }

    monkeypatch.setattr(llm, "_request", fake_request)
    out = llm.chat([{"role": "user", "content": "hi"}], cfg)
    assert out["title"] == "T"
    assert sent["url"].endswith("/api/chat")
    assert sent["body"]["think"] is False and sent["body"]["stream"] is False
    assert sent["body"]["format"]["required"] == ["title", "description", "bullets"]
    assert sent["body"]["model"] == cfg["ollama"]["model"]


def test_chat_wraps_connection_and_http_errors(monkeypatch, cfg):
    def refuse(*_):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setattr(llm, "_request", refuse)
    with pytest.raises(LLMError, match="Cannot reach Ollama"):
        llm.chat([], cfg)

    def http_error(*_):
        raise urllib.error.HTTPError("u", 404, "nf", {}, io.BytesIO(b"model not found"))

    monkeypatch.setattr(llm, "_request", http_error)
    with pytest.raises(LLMError, match="HTTP 404: model not found"):
        llm.chat([], cfg)


def test_unavailable_reason(monkeypatch, cfg):
    model = cfg["ollama"]["model"]
    monkeypatch.setattr(llm, "_request", lambda *_: {"models": [{"name": model}]})
    assert unavailable_reason(cfg) is None
    monkeypatch.setattr(llm, "_request", lambda *_: {"models": [{"name": "other:1b"}]})
    assert "ollama pull" in unavailable_reason(cfg)

    def refuse(*_):
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(llm, "_request", refuse)
    assert "not running" in unavailable_reason(cfg)
