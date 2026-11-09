"""Export texts and compliance results as CSV (one row per text) or JSON (every attempt, every finding)."""

from __future__ import annotations

import json
from dataclasses import asdict

import pandas as pd

from .checker import problems, rule_status
from .pipeline import Result, to_dict


def to_rows(results: list[Result], products: dict) -> list[dict]:
    rows = []
    for r in results:
        final = r.final
        bullets = (final.copy.get("bullets", []) + ["", "", ""])[:3]
        rows.append(
            {
                "sku": r.sku,
                "product": products[r.sku]["name"],
                "brand": r.brand,
                "lang": r.lang,
                "status": final.status,
                **{f"rule_{k}": v for k, v in rule_status(final.findings).items()},
                "revised": r.revised,
                "title": final.copy.get("title", ""),
                "description": final.copy.get("description", ""),
                "bullet_1": bullets[0],
                "bullet_2": bullets[1],
                "bullet_3": bullets[2],
                "issues": " | ".join(problems(final.findings, "warning")),
                "seconds": round(sum(a.seconds for a in r.attempts), 2),
                "model": r.model,
            }
        )
    return rows


def to_csv(results: list[Result], products: dict) -> bytes:
    """UTF-8 with BOM so Excel opens accented text correctly."""
    columns = list(to_rows(results[:1], products)[0]) if results else []
    return (
        pd.DataFrame(to_rows(results, products), columns=columns)
        .to_csv(index=False)
        .encode("utf-8-sig")
    )


def to_json(results: list[Result]) -> str:
    out = []
    for r in results:
        d = to_dict(r)
        for attempt, a in zip(d["attempts"], r.attempts, strict=True):
            attempt["status"] = a.status
            attempt["rules"] = rule_status(a.findings)
            attempt["findings"] = [asdict(f) for f in a.findings]
        d["status"] = r.final.status
        out.append(d)
    return json.dumps(out, ensure_ascii=False, indent=2)
