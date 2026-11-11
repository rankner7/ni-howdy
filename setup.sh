#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/setup_audio.py
.venv/bin/python scripts/setup_recordings.py
echo 'Setup complete. Start the app with ./run.sh'
