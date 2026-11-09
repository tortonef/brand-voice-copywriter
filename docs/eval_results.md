# Evaluation results

Generated on 2026-11-09 with `qwen3.5:4b` via Ollama (Windows, AMD64). 14 products x 2 brands x 3 languages = 84 texts.
Reproduce with `python -m brand_voice.evaluate` (needs Ollama).

A text is **compliant** when no rule fails (warnings allowed).

| Metric | Value |
|---|---|
| Compliant on the first attempt | 68/84 (81%) |
| Compliant after one automatic revision | 82/84 (98%) |
| Fully clean after revision (no warnings either) | 57/84 (68%) |
| Texts that needed a revision | 16/84 (19%) |
| Average time per model call | 5.1 s |
| Average time per finished text (incl. revision) | 6.0 s |
| Slowest call (includes loading the model) | 6.0 s |

## Which rules failed

Number of texts where each rule failed, on the first attempt and after the revision.

| Rule | First attempt | After revision |
|---|---|---|
| Length | 11 | 2 |
| Banned words | 3 | 0 |
| Unsupported claims | 3 | 0 |
| Language | 0 | 0 |

## By brand and language (compliant after revision)

| | en | fr | it |
|---|---|---|---|
| Maison Lumen | 13/14 | 13/14 | 14/14 |
| Riot Thread | 14/14 | 14/14 | 14/14 |

## Texts still failing after the revision

- RT-0002 / Maison Lumen / en: description: Description has 49 words (brand range 60-90); add about 2 full sentences (aim for about 75 words).
- RT-0004 / Maison Lumen / fr: description: Description has 49 words (brand range 60-90); add about 2 full sentences (aim for about 75 words).

## Warnings left for human review (after revision)

- Length: 23
- Generic sustainability claim: 4

The checker only sees what its rules cover. A clean report does not prove that every
detail in a text is true: a person still reviews the copy before it goes live.
