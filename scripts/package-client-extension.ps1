# Package client-extension/ as a ZIP for upload on Releases admin page.
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$src = Join-Path $root "client-extension"
$outDir = Join-Path $root "dist"
$zip = Join-Path $outDir "github-scraper-client-extension.zip"

if (-not (Test-Path $src)) {
    Write-Error "client-extension folder not found: $src"
    exit 1
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
if (Test-Path $zip) { Remove-Item $zip -Force }

Compress-Archive -Path (Join-Path $src "*") -DestinationPath $zip -Force
Write-Host "Created: $zip"
Write-Host "Upload this ZIP in Admin -> Releases and check 'Set as example'."
