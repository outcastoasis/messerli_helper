param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot
$specFile = Join-Path $repoRoot "MesserliHelper.spec"
$metadataScript = Join-Path $repoRoot "packaging\windows\write_build_metadata.py"

if (-not (Test-Path $specFile)) {
    throw "Spec-Datei nicht gefunden: $specFile"
}

if (-not (Test-Path $metadataScript)) {
    throw "Metadata-Skript nicht gefunden: $metadataScript"
}

try {
    python -m PyInstaller --version | Out-Null
}
catch {
    throw "PyInstaller ist nicht installiert. Führe zuerst 'python -m pip install -r requirements-dev.txt' aus."
}

python $metadataScript
if ($LASTEXITCODE -ne 0) {
    throw "Build-Metadaten konnten nicht erzeugt werden (Exit Code $LASTEXITCODE)."
}

$env:PYINSTALLER_ONEFILE = if ($OneFile) { "1" } else { "0" }

try {
    $arguments = @(
        "--noconfirm",
        "--clean",
        $specFile
    )
    python -m PyInstaller @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller-Build fehlgeschlagen (Exit Code $LASTEXITCODE)."
    }
}
finally {
    Remove-Item Env:PYINSTALLER_ONEFILE -ErrorAction SilentlyContinue
}

if ($OneFile) {
    Write-Host ""
    Write-Host "Build fertig: dist\MesserliHelper.exe"
}
else {
    Write-Host ""
    Write-Host "Build fertig: dist\MesserliHelper\MesserliHelper.exe"
}
