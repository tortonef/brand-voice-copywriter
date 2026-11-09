"""Load and validate the committed inputs: products, brand guidelines, claim lexicon, seeded examples."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

BRAND_KEYS = (
    "name",
    "positioning",
    "audience",
    "tone",
    "do",
    "dont",
    "vocabulary",
    "banned_words",
    "length",
    "examples",
)


def _read_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _read_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_products(path: Path, schema_path: Path) -> dict[str, dict]:
    """Return products by SKU; raise ValueError if any record breaks the shared schema."""
    validator = Draft202012Validator(_read_json(schema_path))
    products = {}
    for p in _read_json(path):
        errors = [e.message for e in validator.iter_errors(p)]
        if errors:
            raise ValueError(f"{p.get('sku', '?')}: {'; '.join(errors)}")
        products[p["sku"]] = p
    return products


def load_brands(folder: Path) -> dict[str, dict]:
    """Return brand guidelines keyed by file stem (e.g. 'maison-lumen')."""
    brands = {}
    for path in sorted(folder.glob("*.yaml")):
        brand = _read_yaml(path)
        missing = [k for k in BRAND_KEYS if k not in brand]
        if missing:
            raise ValueError(f"{path.name}: missing keys {missing}")
        brands[path.stem] = brand
    return brands


def load_lexicon(path: Path) -> dict:
    """Return the risky-claim lexicon (see config/claims.yaml)."""
    return _read_yaml(path)


def load_seeded(path: Path) -> list[dict]:
    """Return the hand-written texts with deliberate violations used by the checker demo."""
    return _read_json(path)
