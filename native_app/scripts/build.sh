#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m pip install -U pip setuptools wheel
python3 -m pip install -e . pyinstaller
python3 -m PyInstaller --name pss-logger-native --windowed --onefile --paths "$ROOT_DIR" run.py

echo "Build generado en native_app/dist/"
