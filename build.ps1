# Packages the addon into a zip Blender's Extensions system can install.
$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$distDir = Join-Path $root "dist"
$zipPath = Join-Path $distDir "misko_dizaineris.zip"

New-Item -ItemType Directory -Force -Path $distDir | Out-Null
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }

$files = @("blender_manifest.toml", "LICENSE", "CHANGELOG.md", "__init__.py", "generator.py", "operators.py", "exporter.py", "ui.py")
$tempDir = Join-Path $distDir "misko_dizaineris"
if (Test-Path $tempDir) { Remove-Item $tempDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $tempDir | Out-Null

foreach ($f in $files) {
    Copy-Item (Join-Path $root $f) (Join-Path $tempDir $f)
}

Compress-Archive -Path (Join-Path $tempDir "*") -DestinationPath $zipPath
Remove-Item $tempDir -Recurse -Force

Write-Host "Built $zipPath"
