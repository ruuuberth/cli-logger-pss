#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m pip install -r requirements.txt pyinstaller
python3 -m PyInstaller --name pss-logger-native --windowed --onefile app/main.py

echo "Build generado en native_app/dist/"
