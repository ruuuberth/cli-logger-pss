#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m pip install -U pip setuptools wheel
python3 -m pip install -e . pyinstaller
python3 -m PyInstaller --name pss-logger-native --windowed --onefile --paths "$ROOT_DIR" --collect-data app.services run.py

PACKAGE_ARGS=(
  scripts/package_portable.py
  --platform linux
  --app-binary "$ROOT_DIR/dist/pss-logger-native"
  --output-dir dist
)

if [ -n "${MITMPROXY_BUNDLE_DIR:-}" ]; then
  PACKAGE_ARGS+=(--mitmproxy-bundle-dir "$MITMPROXY_BUNDLE_DIR")
fi
if [ -n "${MITMPROXY_FALLBACK_BINARY:-}" ]; then
  PACKAGE_ARGS+=(--mitmproxy-fallback-binary "$MITMPROXY_FALLBACK_BINARY")
fi

python3 "${PACKAGE_ARGS[@]}"

echo "Build generado en native_app/dist/"
