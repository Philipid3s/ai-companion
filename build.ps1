param(
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$DistRoot = Join-Path $ProjectRoot 'dist\AIWindowsCompanion'
$MemoryNotes = Join-Path $DistRoot 'memory\notes'
$ConfigTarget = Join-Path $DistRoot 'config.yaml'
$SanitizedConfigSource = Join-Path $ProjectRoot 'config.example.yaml'
$LocalConfigSource = Join-Path $ProjectRoot 'config.yaml'

if ($Clean) {
    Remove-Item -Recurse -Force (Join-Path $ProjectRoot 'build') -ErrorAction SilentlyContinue
    Remove-Item -Recurse -Force (Join-Path $ProjectRoot 'dist') -ErrorAction SilentlyContinue
}

python -m PyInstaller --noconfirm (Join-Path $ProjectRoot 'AIWindowsCompanion.spec')

New-Item -ItemType Directory -Force $MemoryNotes | Out-Null
if (-not (Test-Path $ConfigTarget)) {
    if (Test-Path $SanitizedConfigSource) {
        Copy-Item $SanitizedConfigSource $ConfigTarget
    } else {
        Copy-Item $LocalConfigSource $ConfigTarget
    }
}

Write-Host "Build complete: $DistRoot\AIWindowsCompanion.exe"
