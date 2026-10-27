# Recommended way to start the API on Windows (low-impact, no reload by default)
param(
    [switch]$Install,
    [switch]$InstallOnly,
    [int]$Port = 8000,
    [int]$Workers = 1
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

try {
    [System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = `
        [System.Diagnostics.ProcessPriorityClass]::BelowNormal
} catch {
    Write-Host "Note: could not lower process priority." -ForegroundColor DarkYellow
}

$env:PYTHONPATH = "."
$env:API_PORT = "$Port"
$env:API_WORKERS = "$Workers"
$env:API_ENABLE_SCHEDULER = "true"
$env:API_RELOAD = "false"
$env:GITHUB_SCRAPER_PROFILE_WORKERS = "6"
$env:GITHUB_SCRAPER_PROFILE_CHUNK = "20"
$env:GITHUB_SCRAPER_GRAPHQL_BATCH = "25"
$env:GITHUB_SCRAPER_REQUEST_DELAY_MIN = "0.12"
$env:GITHUB_SCRAPER_REQUEST_DELAY_MAX = "0.35"

$requirements = Join-Path $PSScriptRoot "requirements.txt"

if ($Install) {
    Write-Host "Installing Python dependencies from $requirements ..." -ForegroundColor Cyan
    if (-not (Test-Path $requirements)) {
        Write-Host "Requirements file not found: $requirements" -ForegroundColor Red
        exit 1
    }

    $sitePackages = python -c "import site; print(site.getsitepackages()[0])" 2>$null
    if ($sitePackages) {
        Get-ChildItem -Path $sitePackages -Filter "~*" -Directory -ErrorAction SilentlyContinue | ForEach-Object {
            Write-Host "Removing invalid package folder: $($_.Name)" -ForegroundColor Yellow
            Remove-Item -LiteralPath $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
        }
    }

    python -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) {
        Write-Host "pip install failed." -ForegroundColor Red
        exit 1
    }
}

if ($InstallOnly) {
    exit 0
}

Write-Host "Verifying app imports..." -ForegroundColor Cyan
python -c "from app.main import app; print('OK:', app.title)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Import check failed. Run: .\start-project.ps1 -Install" -ForegroundColor Red
    exit 1
}

if ($Workers -lt 1) {
    $Workers = 1
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
. (Join-Path $repoRoot "project-ports.ps1")

Write-Host "Checking port $Port is available..." -ForegroundColor Cyan
if (-not (Test-PortBindable -Port $Port)) {
    Write-Host "Port $Port is busy. Stopping existing project server..." -ForegroundColor Yellow
    [void](Stop-ProjectServers -Ports @($Port) -CloseShellWindows)
    if (-not (Wait-PortBindable -Port $Port -TimeoutSec 20)) {
        Write-Host "Port $Port is still in use (including orphaned uvicorn workers)." -ForegroundColor Red
        [void](Ensure-ProjectPortsFree -Ports @($Port) -CloseShellWindows)
        exit 1
    }
}

Write-Host "Starting GitHub Scraper API on http://127.0.0.1:$Port with $Workers worker(s) ..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the API." -ForegroundColor DarkGray

if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    if ($Workers -le 1) {
        python -m uvicorn app.main:app --host 0.0.0.0 --port $Port
    } else {
        python -m uvicorn app.main:app --host 0.0.0.0 --port $Port --workers $Workers
    }
    exit $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousErrorAction
}
