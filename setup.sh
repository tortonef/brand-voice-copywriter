#!/usr/bin/env bash
# macOS/Linux setup: creates .venv, installs dependencies, pulls the local LLM with Ollama, runs a smoke check.
# Safe to run more than once. Usage: bash setup.sh
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUTF8=1

if [ ! -x .venv/bin/python ]; then
  PYTHON="$(command -v python3.12 || command -v python3 || true)"
  [ -n "$PYTHON" ] || { echo "Python 3.12 not found. Install it from python.org."; exit 1; }
  echo "==> Create virtual environment ($PYTHON)"
  "$PYTHON" -m venv .venv
fi
PY=.venv/bin/python
"$PY" -c "import sys; assert sys.version_info[:2] == (3, 12), 'Python 3.12 is required, found ' + sys.version"
echo "==> Upgrade pip"; "$PY" -m pip install --quiet --upgrade pip
echo "==> Install dependencies"; "$PY" -m pip install --quiet -r requirements.txt -r requirements-dev.txt
echo "==> Install this package"; "$PY" -m pip install --quiet --no-deps -e .
if command -v ollama >/dev/null 2>&1; then
  MODEL="$("$PY" -c "from brand_voice.config import load_config; print(load_config()['ollama']['model'])")"
  echo "==> Pull local LLM $MODEL with Ollama (first run only, ~3.3 GB)"; ollama pull "$MODEL"
else
  echo
  echo "[!] Ollama not found. The app will open in demo mode with pre-generated texts."
  echo "    To generate live: install it from https://ollama.com/download, then run this setup again."
  echo
fi
echo "==> Smoke check"; "$PY" -m brand_voice.smoke
echo; echo "Setup complete. Start the app with: bash run.sh"
