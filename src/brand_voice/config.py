"""Load config.yaml with environment-variable overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[2]
ENV_PREFIX = "BRAND_VOICE_"


def _override(data: dict[str, Any], prefix: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        env_key = f"{prefix}{key}".upper()
        if isinstance(value, dict):
            out[key] = _override(value, env_key + "_")
        elif env_key in os.environ:
            # Parse with YAML so numbers and booleans keep their type.
            out[key] = yaml.safe_load(os.environ[env_key])
        else:
            out[key] = value
    return out


def load_config(path: Path | None = None) -> dict[str, Any]:
    """Return the config with env overrides applied; relative paths are resolved from the repo root."""
    path = path or ROOT / "config.yaml"
    with path.open(encoding="utf-8") as f:
        cfg = _override(yaml.safe_load(f), ENV_PREFIX)
    cfg["paths"] = {k: ROOT / v for k, v in cfg["paths"].items()}
    return cfg
