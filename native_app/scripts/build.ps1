$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RootDir

python -m pip install -U pip setuptools wheel
python -m pip install -e . pyinstaller
$buildVersion = if ($env:PSS_BUILD_VERSION) { $env:PSS_BUILD_VERSION } else { (git describe --tags --always 2>$null) }
if (-not $buildVersion) { $buildVersion = "0.1.0" }
$buildSha = if ($env:PSS_BUILD_GIT_SHA) { $env:PSS_BUILD_GIT_SHA } else { (git rev-parse --short HEAD 2>$null) }
if (-not $buildSha) { $buildSha = "unknown" }
$buildTime = if ($env:PSS_BUILD_TIME) { $env:PSS_BUILD_TIME } else { (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") }
$buildSource = if ($env:PSS_BUILD_SOURCE) { $env:PSS_BUILD_SOURCE } else { "build-script" }
$metadataFile = Join-Path $env:TEMP ("pss_build_metadata_" + [guid]::NewGuid().ToString("N") + ".json")
$metadataJson = "{`"version`":`"$buildVersion`",`"git_sha`":`"$buildSha`",`"build_time`":`"$buildTime`",`"source`":`"$buildSource`"}"
Set-Content -Path $metadataFile -Value $metadataJson -Encoding UTF8

try {
  python -m PyInstaller --name pss-logger-native --windowed --onefile --paths "$RootDir" --collect-data app.services --add-data "$RootDir/app/services/mitm_api_flow_addon.py;app/services" --add-data "$metadataFile;app/resources" run.py
}
finally {
  if (Test-Path $metadataFile) {
    Remove-Item $metadataFile -Force
  }
}

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
