# Build the portable Windows bundle.
# Usage:  powershell -ExecutionPolicy Bypass -File build.ps1
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is missing. Install build dependencies: python -m pip install -e '.[dev,build]'"
}
python -m ruff --version *> $null
if ($LASTEXITCODE -ne 0) {
    throw "ruff is missing. Install dev dependencies: python -m pip install -e '.[dev,build]'"
}

Write-Host "==> Lint" -ForegroundColor Cyan
python -m ruff check src scripts tests

Write-Host "==> Tests" -ForegroundColor Cyan
python -m pytest -q

if (-not (Test-Path "data\worlddata.sqlite")) {
    Write-Host "==> No dataset found; refreshing from sources" -ForegroundColor Cyan
    python scripts/refresh_data.py
}

Write-Host "==> PyInstaller" -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean WorldDataComparison.spec

$out = "dist\WorldDataComparison"
if (-not (Test-Path "$out\WorldDataComparison.exe")) {
    throw "Build did not produce $out\WorldDataComparison.exe"
}

Write-Host "==> Assemble the portable layout (data and config beside the exe)" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path "$out\data" | Out-Null
Copy-Item -LiteralPath "data\worlddata.sqlite" -Destination "$out\data\" -Force
Copy-Item -LiteralPath "data\manifest.json" -Destination "$out\data\" -Force
Copy-Item -LiteralPath "data\quality_report.csv" -Destination "$out\data\" -Force
Copy-Item -LiteralPath "data\rejected.csv" -Destination "$out\data\" -Force
New-Item -ItemType Directory -Force -Path "$out\config" | Out-Null
Copy-Item -Path "config\*" -Destination "$out\config" -Recurse -Force
New-Item -ItemType Directory -Force -Path "$out\docs" | Out-Null
Copy-Item -Path "docs\*" -Destination "$out\docs" -Recurse -Force
Copy-Item -LiteralPath "NOTICE.txt" -Destination "$out\" -Force
Copy-Item -LiteralPath "README.md" -Destination "$out\" -Force
Copy-Item -LiteralPath "LICENSE" -Destination "$out\" -Force
Copy-Item -LiteralPath "CHANGELOG.md" -Destination "$out\" -Force
Copy-Item -LiteralPath "CITATION.cff" -Destination "$out\" -Force
Copy-Item -LiteralPath "CONTRIBUTING.md" -Destination "$out\" -Force
Copy-Item -LiteralPath "CODE_OF_CONDUCT.md" -Destination "$out\" -Force
Copy-Item -LiteralPath "SECURITY.md" -Destination "$out\" -Force
Copy-Item -LiteralPath "SUPPORT.md" -Destination "$out\" -Force
Copy-Item -LiteralPath "ROADMAP.md" -Destination "$out\" -Force

Write-Host "==> Smoke-test the packaged application" -ForegroundColor Cyan
$proc = Start-Process -FilePath "$out\WorldDataComparison.exe" -ArgumentList "--selftest" -Wait -PassThru
if ($proc.ExitCode -ne 0) {
    throw "Packaged self-test failed with exit code $($proc.ExitCode)"
}

Write-Host "==> Clean transient files before zipping" -ForegroundColor Cyan
Remove-Item -LiteralPath "$out\data\settings.json" -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "$out\data\worlddata.sqlite-shm" -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "$out\data\worlddata.sqlite-wal" -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "$out\selftest.log" -ErrorAction SilentlyContinue
# The portable copies beside the exe are authoritative; drop the duplicate bundle.
Remove-Item -LiteralPath "$out\_internal\data" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "$out\_internal\config" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath "$out\_internal\docs" -Recurse -Force -ErrorAction SilentlyContinue

$version = python -c "import worlddata; print(worlddata.__version__)"
$zip = "dist\WorldDataComparison-$version.zip"
if (Test-Path $zip) { Remove-Item -LiteralPath $zip }
Compress-Archive -Path "$out\*" -DestinationPath $zip
Write-Host "==> Done: $zip" -ForegroundColor Green
