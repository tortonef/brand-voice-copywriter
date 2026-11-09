"""Generate -> check -> (at most one) revision. Results serialize to plain dicts for samples and export."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field

from . import llm
from .checker import Finding, check, overall, problems
from .prompt import build_messages, revision_messages


@dataclass
class Attempt:
    copy: dict
    seconds: float
    findings: list[Finding] = field(default_factory=list)

    @property
    def status(self) -> str:
        return overall(self.findings)


@dataclass
class Result:
    sku: str
    brand: str  # brand id, e.g. "maison-lumen"
    lang: str
    model: str
    attempts: list[Attempt]

    @property
    def final(self) -> Attempt:
        return self.attempts[-1]

    @property
    def revised(self) -> bool:
        return len(self.attempts) > 1


def generate(
    product: dict,
    brand_id: str,
    brand: dict,
    lang: str,
    lexicon: dict,
    cfg: dict,
    chat: Callable[[list[dict], dict], dict] = llm.chat,
) -> Result:
    """First attempt; if any rule fails, one revision with the failures as feedback."""
    messages = build_messages(product, brand, lang)
    attempts = []
    for _ in range(2):
        start = time.perf_counter()
        copy = chat(messages, cfg)
        seconds = time.perf_counter() - start
        findings = check(copy, product, brand, lang, lexicon)
        attempts.append(Attempt(copy, seconds, findings))
        issues = problems(findings)
        if not issues:
            break
        messages = revision_messages(messages, copy, issues)
    return Result(product["sku"], brand_id, lang, cfg["ollama"]["model"], attempts)


def to_dict(result: Result) -> dict:
    """Texts and timings only; compliance is recomputed live when loaded."""
    return {
        "sku": result.sku,
        "brand": result.brand,
        "lang": result.lang,
        "model": result.model,
        "attempts": [{"copy": a.copy, "seconds": round(a.seconds, 2)} for a in result.attempts],
    }


def from_dict(d: dict, products: dict, brands: dict, lexicon: dict) -> Result:
    """Rebuild a result and re-run the checker on every attempt."""
    product, brand = products[d["sku"]], brands[d["brand"]]
    attempts = [
        Attempt(a["copy"], a["seconds"], check(a["copy"], product, brand, d["lang"], lexicon))
        for a in d["attempts"]
    ]
    return Result(d["sku"], d["brand"], d["lang"], d["model"], attempts)
