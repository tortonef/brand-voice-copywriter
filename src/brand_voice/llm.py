"""Minimal Ollama client (standard library only): structured JSON output, thinking disabled."""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from .prompt import OUTPUT_SCHEMA


class LLMError(RuntimeError):
    """Ollama is unreachable or returned output we cannot use."""


def parse_copy(text: str) -> dict:
    """Parse the model's JSON answer into {title, description, bullets}, or raise LLMError.

    The bullet count is not enforced here: the checker reports it, so a revision can fix it.
    """
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMError(f"Model output is not valid JSON ({e.msg}): {text[:200]!r}") from e
    if not isinstance(obj, dict):
        raise LLMError(f"Model output is not a JSON object: {text[:200]!r}")
    title, description, bullets = obj.get("title"), obj.get("description"), obj.get("bullets")
    if not isinstance(title, str) or not isinstance(description, str):
        raise LLMError(f"Model output needs string 'title' and 'description': {text[:200]!r}")
    if not isinstance(bullets, list) or not all(isinstance(b, str) for b in bullets):
        raise LLMError(f"Model output needs 'bullets' as a list of strings: {text[:200]!r}")
    return {
        "title": title.strip(),
        "description": " ".join(description.split()),
        "bullets": [b.strip() for b in bullets],
    }


def _request(url: str, body: dict | None, timeout: float) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def chat(messages: list[dict], cfg: dict) -> dict:
    """Send one chat request and return the parsed copy."""
    o = cfg["ollama"]
    body = {
        "model": o["model"],
        "messages": messages,
        "stream": False,
        "think": False,
        "format": OUTPUT_SCHEMA,
        "options": {"temperature": o["temperature"]},
    }
    try:
        data = _request(f"{o['host']}/api/chat", body, o["timeout_s"])
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise LLMError(f"Ollama returned HTTP {e.code}: {detail}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise LLMError(f"Cannot reach Ollama at {o['host']}: {e}") from e
    return parse_copy(data.get("message", {}).get("content", ""))


def unavailable_reason(cfg: dict) -> str | None:
    """None if Ollama is running and has the configured model, otherwise a short explanation."""
    o = cfg["ollama"]
    try:
        tags = _request(f"{o['host']}/api/tags", None, 2)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return f"Ollama is not running at {o['host']}."
    names = {m.get("name") for m in tags.get("models", [])}
    if o["model"] not in names and f"{o['model']}:latest" not in names:
        return f"Ollama is running but the model {o['model']} is not pulled (run: ollama pull {o['model']})."
    return None
