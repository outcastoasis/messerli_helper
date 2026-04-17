param(
    [switch]$SkipExeBuild
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $repoRoot

$metadataScript = Join-Path $repoRoot "packaging\windows\write_build_metadata.py"
$installerScript = Join-Path $repoRoot "packaging\windows\MesserliHelperInstaller.iss"

if (-not (Test-Path $metadataScript)) {
    throw "Metadata-Skript nicht gefunden: $metadataScript"
}

if (-not (Test-Path $installerScript)) {
    throw "Installer-Skript nicht gefunden: $installerScript"
}

if (-not $SkipExeBuild) {
    & (Join-Path $repoRoot "build_exe.ps1")
    if ($LASTEXITCODE -ne 0) {
        throw "EXE-Build fehlgeschlagen (Exit Code $LASTEXITCODE)."
    }
}

python $metadataScript
if ($LASTEXITCODE -ne 0) {
    throw "Installer-Metadaten konnten nicht erzeugt werden (Exit Code $LASTEXITCODE)."
}

$isccPath = $null
$isccCommand = Get-Command iscc.exe -ErrorAction SilentlyContinue
if ($null -ne $isccCommand) {
    $isccPath = $isccCommand.Source
}
else {
    $fallbacks = @(
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles} "Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:LocalAppData} "Programs\Inno Setup 6\ISCC.exe")
    )

    foreach ($fallback in $fallbacks) {
        if (Test-Path $fallback) {
            $isccPath = $fallback
            break
        }
    }
}

if ($null -eq $isccPath) {
    throw "ISCC.exe wurde nicht gefunden. Installiere zürst Inno Setup 6."
}

& $isccPath $installerScript
if ($LASTEXITCODE -ne 0) {
    throw "Installer-Build fehlgeschlagen (Exit Code $LASTEXITCODE)."
}
