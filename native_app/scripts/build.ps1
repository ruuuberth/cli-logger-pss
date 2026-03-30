$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RootDir

python -m pip install -U pip setuptools wheel
python -m pip install -e . pyinstaller
python -m PyInstaller --name pss-logger-native --windowed --onefile --paths "$RootDir" --collect-data app.services run.py

Write-Host "Build generado en native_app/dist/"
