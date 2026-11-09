"""Real call to the local model. Needs Ollama running with the default model; excluded from CI."""

import pytest

from brand_voice.llm import unavailable_reason
from brand_voice.pipeline import generate


@pytest.mark.slow
def test_real_generation_returns_three_bullets_in_the_right_language(
    cfg, products, brands, lexicon
):
    reason = unavailable_reason(cfg)
    if reason:
        pytest.skip(reason)
    r = generate(products["RT-0001"], "riot-thread", brands["riot-thread"], "it", lexicon, cfg)
    assert len(r.final.copy["bullets"]) == 3
    assert r.final.copy["title"]
    assert all(f.rule != "language" or f.status != "fail" for f in r.final.findings)
