$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RootDir

python -m pip install -U pip setuptools wheel
python -m pip install -e . pyinstaller
python -m PyInstaller --name pss-logger-native --windowed --onefile --paths "$RootDir" --collect-data app.services run.py

$packageArgs = @(
  "scripts/package_portable.py",
  "--platform", "windows",
  "--app-binary", (Join-Path $RootDir "dist/pss-logger-native.exe"),
  "--output-dir", "dist"
)
if ($env:MITMPROXY_BUNDLE_DIR) {
  $packageArgs += @("--mitmproxy-bundle-dir", $env:MITMPROXY_BUNDLE_DIR)
}
if ($env:MITMPROXY_FALLBACK_BINARY) {
  $packageArgs += @("--mitmproxy-fallback-binary", $env:MITMPROXY_FALLBACK_BINARY)
}
python @packageArgs

Write-Host "Build generado en native_app/dist/"
