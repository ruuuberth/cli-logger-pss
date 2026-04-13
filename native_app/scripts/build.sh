#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

python3 -m pip install -U pip setuptools wheel
python3 -m pip install -e . pyinstaller
BUILD_VERSION="${PSS_BUILD_VERSION:-$(git describe --tags --always 2>/dev/null || echo 0.1.0)}"
BUILD_SHA="${PSS_BUILD_GIT_SHA:-$(git rev-parse --short HEAD 2>/dev/null || echo unknown)}"
BUILD_TIME="${PSS_BUILD_TIME:-$(date -u +%Y-%m-%dT%H:%M:%SZ)}"
BUILD_SOURCE="${PSS_BUILD_SOURCE:-build-script}"
BUILD_METADATA_FILE="$(mktemp)"
trap 'rm -f "$BUILD_METADATA_FILE"' EXIT
cat > "$BUILD_METADATA_FILE" <<EOF
{"version":"$BUILD_VERSION","git_sha":"$BUILD_SHA","build_time":"$BUILD_TIME","source":"$BUILD_SOURCE"}
EOF

python3 -m PyInstaller \
  --name pss-logger-native \
  --windowed \
  --onefile \
  --paths "$ROOT_DIR" \
  --collect-data app.services \
  --add-data "$ROOT_DIR/app/services/mitm_api_flow_addon.py:app/services" \
  --add-data "$BUILD_METADATA_FILE:app/resources" \
  run.py

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
