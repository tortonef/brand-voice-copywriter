#!/usr/bin/env bash
# Launch the app. Usage: bash run.sh
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUTF8=1
[ -x .venv/bin/python ] || { echo "Run setup.sh first."; exit 1; }
exec .venv/bin/python -m streamlit run app.py
