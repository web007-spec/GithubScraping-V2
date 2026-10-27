# Start Next.js on port 3001 in low-impact mode.
param(
    [switch]$Install,
    [switch]$InstallOnly,
    [int]$Port = 3001
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

try {
    [System.Diagnostics.Process]::GetCurrentProcess().PriorityClass = `
        [System.Diagnostics.ProcessPriorityClass]::BelowNormal
} catch {
    Write-Host "Note: could not lower process priority." -ForegroundColor DarkYellow
}

$env:PORT = $Port
$env:NODE_OPTIONS = "--max-old-space-size=2048"
$env:NEXT_TELEMETRY_DISABLED = "1"
$env:NEXT_BUILD_CPUS = "2"
$env:DISABLE_HMR = "1"

$NextBin = Join-Path $PSScriptRoot "node_modules\next\dist\bin\next"

if ($Install -or -not (Test-Path $NextBin)) {
    Write-Host "Installing frontend dependencies (npm install) ..." -ForegroundColor Cyan
    npm install
    if ($LASTEXITCODE -ne 0) {
        Write-Host "npm install failed." -ForegroundColor Red
        exit 1
    }
}

if ($InstallOnly) {
    exit 0
}

if (-not (Test-Path $NextBin)) {
    Write-Host "Next.js not found. Run: .\start-project.ps1 -Install" -ForegroundColor Red
    exit 1
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
. (Join-Path $repoRoot "project-ports.ps1")

Write-Host "Checking port $Port is available..." -ForegroundColor Cyan
if (-not (Test-PortBindable -Port $Port)) {
    Write-Host "Port $Port is busy. Stopping existing frontend..." -ForegroundColor Yellow
    [void](Stop-ProjectServers -Ports @($Port) -CloseShellWindows)
    if (-not (Wait-PortBindable -Port $Port -TimeoutSec 20)) {
        Write-Host "Port $Port is still in use." -ForegroundColor Red
        [void](Ensure-ProjectPortsFree -Ports @($Port) -CloseShellWindows)
        exit 1
    }
}

Write-Host "Starting frontend on http://127.0.0.1:$Port (webpack dev mode) ..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the frontend." -ForegroundColor DarkGray

if ($PSVersionTable.PSVersion.Major -ge 7) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$previousErrorAction = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    node --max-old-space-size=2048 $NextBin dev --webpack -H 0.0.0.0 -p $Port
    exit $LASTEXITCODE
} finally {
    $ErrorActionPreference = $previousErrorAction
}
