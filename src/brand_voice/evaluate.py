"""Generate copy for every product x brand x language, measure compliance, write the report.

Usage: python -m brand_voice.evaluate [--limit N]
Writes docs/eval_results.md and the demo-mode samples in data/sample_outputs/ (one file per brand),
so the pre-generated texts in the app are exactly the ones evaluated here. Needs Ollama running.
"""

from __future__ import annotations

import argparse
import json
import platform
from datetime import date

from .checker import RULE_LABELS, RULES, problems, rule_status
from .config import load_config
from .data import load_brands, load_lexicon, load_products
from .llm import unavailable_reason
from .pipeline import Result, generate, to_dict


def _pct(n: int, d: int) -> str:
    return f"{n / d:.0%}" if d else "n/a"


def _ok(attempt) -> bool:
    return attempt.status != "fail"


def report(results: list[Result], brands: dict, products: dict, model: str) -> str:
    """Markdown report. Only counts and averages from this run; no external numbers."""
    n = len(results)
    first_ok = sum(_ok(r.attempts[0]) for r in results)
    final_ok = sum(_ok(r.final) for r in results)
    clean = sum(r.final.status == "pass" for r in results)
    revised = sum(r.revised for r in results)
    calls = [a.seconds for r in results for a in r.attempts]
    per_text = [sum(a.seconds for a in r.attempts) for r in results]

    lines = [
        "# Evaluation results",
        "",
        f"Generated on {date.today().isoformat()} with `{model}` via Ollama "
        f"({platform.system()}, {platform.machine()}). "
        f"{len(products)} products x {len(brands)} brands x "
        f"{len({r.lang for r in results})} languages = {n} texts.",
        "Reproduce with `python -m brand_voice.evaluate` (needs Ollama).",
        "",
        "A text is **compliant** when no rule fails (warnings allowed).",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Compliant on the first attempt | {first_ok}/{n} ({_pct(first_ok, n)}) |",
        f"| Compliant after one automatic revision | {final_ok}/{n} ({_pct(final_ok, n)}) |",
        f"| Fully clean after revision (no warnings either) | {clean}/{n} ({_pct(clean, n)}) |",
        f"| Texts that needed a revision | {revised}/{n} ({_pct(revised, n)}) |",
        f"| Average time per model call | {sum(calls) / len(calls):.1f} s |",
        f"| Average time per finished text (incl. revision) | {sum(per_text) / n:.1f} s |",
        f"| Slowest call (includes loading the model) | {max(calls):.1f} s |",
        "",
        "## Which rules failed",
        "",
        "Number of texts where each rule failed, on the first attempt and after the revision.",
        "",
        "| Rule | First attempt | After revision |",
        "|---|---|---|",
    ]
    for rule in RULES:
        before = sum(rule_status(r.attempts[0].findings)[rule] == "fail" for r in results)
        after = sum(rule_status(r.final.findings)[rule] == "fail" for r in results)
        lines.append(f"| {RULE_LABELS[rule]} | {before} | {after} |")

    lines += [
        "",
        "## By brand and language (compliant after revision)",
        "",
        "| | " + " | ".join(sorted({r.lang for r in results})) + " |",
        "|---|" + "---|" * len({r.lang for r in results}),
    ]
    for brand_id in sorted({r.brand for r in results}):
        cells = []
        for lang in sorted({r.lang for r in results}):
            group = [r for r in results if r.brand == brand_id and r.lang == lang]
            cells.append(f"{sum(_ok(r.final) for r in group)}/{len(group)}")
        lines.append(f"| {brands[brand_id]['name']} | " + " | ".join(cells) + " |")

    failing = [r for r in results if not _ok(r.final)]
    lines += ["", "## Texts still failing after the revision", ""]
    if not failing:
        lines.append("None.")
    for r in failing:
        issues = "; ".join(problems(r.final.findings))
        lines.append(f"- {r.sku} / {brands[r.brand]['name']} / {r.lang}: {issues}")

    warnings: dict[str, int] = {}
    for r in results:
        for f in r.final.findings:
            if f.status == "warning":
                key = f.message.split('"')[0].strip() if f.rule == "claims" else RULE_LABELS[f.rule]
                warnings[key] = warnings.get(key, 0) + 1
    lines += ["", "## Warnings left for human review (after revision)", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(warnings.items(), key=lambda kv: -kv[1])] or [
        "None."
    ]
    lines += [
        "",
        "The checker only sees what its rules cover. A clean report does not prove that every",
        "detail in a text is true: a person still reviews the copy before it goes live.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--limit", type=int, help="only the first N products per brand (quick check)"
    )
    args = parser.parse_args(argv)

    cfg = load_config()
    paths = cfg["paths"]
    reason = unavailable_reason(cfg)
    if reason:
        raise SystemExit(f"{reason} Start Ollama and try again.")
    products = load_products(paths["products"], paths["schema"])
    brands = load_brands(paths["brands"])
    lexicon = load_lexicon(paths["claims"])
    skus = list(products)
    if args.limit:
        skus = [s for b in ("ML", "RT") for s in skus if s.startswith(b)][: args.limit * 2]

    results = []
    total = len(brands) * len(skus) * len(cfg["languages"])
    for brand_id, brand in brands.items():
        for sku in skus:
            for lang in cfg["languages"]:
                r = generate(products[sku], brand_id, brand, lang, lexicon, cfg)
                results.append(r)
                print(
                    f"[{len(results)}/{total}] {brand_id} {sku} {lang}: "
                    f"{r.attempts[0].status} -> {r.final.status} "
                    f"({sum(a.seconds for a in r.attempts):.1f} s)",
                    flush=True,
                )

    paths["samples"].mkdir(parents=True, exist_ok=True)
    for brand_id in brands:
        out = [to_dict(r) for r in results if r.brand == brand_id]
        with (paths["samples"] / f"{brand_id}.json").open("w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
            f.write("\n")
    with paths["eval_report"].open("w", encoding="utf-8") as f:
        f.write(report(results, brands, products, cfg["ollama"]["model"]))
    print(f"Wrote {paths['eval_report']} and {len(brands)} sample file(s) in {paths['samples']}")


if __name__ == "__main__":
    main()
