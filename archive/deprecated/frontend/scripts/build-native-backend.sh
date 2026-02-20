#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
OUTPUT_DIR="$ROOT_DIR/frontend/native-backend"

mkdir -p "$OUTPUT_DIR/dist" "$OUTPUT_DIR/build"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 no esta disponible en PATH" >&2
  exit 1
fi

cd "$BACKEND_DIR"
python3 -m pip install -r requirements.txt pyinstaller

python3 -m PyInstaller \
  --name pss-backend \
  --onefile \
  --clean \
  --noconfirm \
  --paths "$BACKEND_DIR" \
  --distpath "$OUTPUT_DIR/dist" \
  --workpath "$OUTPUT_DIR/build" \
  app/desktop_main.py

echo "Backend nativo generado en: $OUTPUT_DIR/dist"
