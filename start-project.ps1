# Start the management API and Next.js frontend together (Windows).
param(
    [switch]$Install,
    [int]$FrontendPort = 3001,
    [int]$BackendPort = 8000,
    [int]$BackendWorkers = 1,
    [ValidateSet("Minimized", "Normal", "Hidden")]
    [string]$WindowStyle = "Normal",
    [int]$StartupTimeoutSec = 180
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

. (Join-Path $Root "project-ports.ps1")

$backendDir = Join-Path $Root "backend\github_Scraping"
$frontendDir = Join-Path $Root "frontend"
$backendScript = Join-Path $backendDir "start-api.ps1"
$frontendScript = Join-Path $frontendDir "start-frontend.ps1"

foreach ($path in @($backendScript, $frontendScript)) {
    if (-not (Test-Path $path)) {
        Write-Host "Required script not found: $path" -ForegroundColor Red
        exit 1
    }
}

function Test-PortReady {
    param([int]$Port)
    return Test-PortListening -Port $Port
}

function Wait-ForPort {
    param(
        [int]$Port,
        [string]$Label,
        [int]$TimeoutSec
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortReady -Port $Port) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Start-ServiceWindow {
    param(
        [string]$ScriptPath,
        [string]$WorkingDirectory,
        [string[]]$ExtraArgs,
        [System.Diagnostics.ProcessWindowStyle]$Style
    )

    $quotedScript = "`"$ScriptPath`""
    $argString = "-NoExit -ExecutionPolicy Bypass -File $quotedScript"
    foreach ($arg in $ExtraArgs) {
        if ($arg -match '\s') {
            $argString += " `"$arg`""
        } else {
            $argString += " $arg"
        }
    }

    return Start-Process powershell.exe `
        -ArgumentList $argString `
        -WorkingDirectory $WorkingDirectory `
        -WindowStyle $Style `
        -PassThru
}

Write-Host "Starting GitHub Scraper project..." -ForegroundColor Cyan
Write-Host "  API:      http://127.0.0.1:$BackendPort  ($BackendWorkers worker(s))" -ForegroundColor Cyan
Write-Host "  Frontend: http://127.0.0.1:$FrontendPort" -ForegroundColor Cyan
Write-Host "  Docs:     http://127.0.0.1:$FrontendPort/explore/docs" -ForegroundColor DarkCyan
Write-Host ""

$stopScript = Join-Path $Root "stop-project.ps1"
if (Test-Path $stopScript) {
    Write-Host "Stopping any existing project processes on these ports..." -ForegroundColor DarkGray
    & $stopScript -Ports "$FrontendPort,$BackendPort" -CloseShellWindows
    $backendFree = Wait-PortBindable -Port $BackendPort -TimeoutSec 20
    $frontendFree = Wait-PortBindable -Port $FrontendPort -TimeoutSec 20
    if (-not $backendFree -or -not $frontendFree) {
        Write-Host "Could not free required ports before startup." -ForegroundColor Red
        if (-not $backendFree) {
            Write-Host "  Port $BackendPort is still in use." -ForegroundColor Red
        }
        if (-not $frontendFree) {
            Write-Host "  Port $FrontendPort is still in use." -ForegroundColor Red
        }
        Write-Host "Run: .\stop-project.ps1 -CloseShellWindows" -ForegroundColor Yellow
        exit 1
    }
    Write-Host ""
}

if ($Install) {
    Write-Host "Installing dependencies in this window first..." -ForegroundColor Cyan

    Push-Location $backendDir
    try {
        & $backendScript -Install -InstallOnly -Port $BackendPort -Workers $BackendWorkers
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Backend install failed." -ForegroundColor Red
            exit 1
        }
    } finally {
        Pop-Location
    }

    Push-Location $frontendDir
    try {
        & $frontendScript -Install -InstallOnly -Port $FrontendPort
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Frontend install failed." -ForegroundColor Red
            exit 1
        }
    } finally {
        Pop-Location
    }

    $indexerDirs = @(
        (Join-Path $Root "backend\google_docs_indexer"),
        (Join-Path $Root "backend\google_drive_indexer")
    )
    foreach ($indexerDir in $indexerDirs) {
        $indexerReq = Join-Path $indexerDir "requirements.txt"
        $indexerPython = Join-Path $indexerDir ".venv\Scripts\python.exe"
        $label = Split-Path $indexerDir -Leaf
        if ((Test-Path $indexerPython) -and (Test-Path $indexerReq)) {
            Write-Host "Installing $label dependencies..." -ForegroundColor Cyan
            Push-Location $indexerDir
            try {
                & $indexerPython -m pip install -r $indexerReq
                if ($LASTEXITCODE -ne 0) {
                    Write-Host "$label install failed." -ForegroundColor Red
                    exit 1
                }
            } finally {
                Pop-Location
            }
        } else {
            Write-Host "Skipping $label deps (create .venv first)." -ForegroundColor DarkYellow
        }
    }

    Write-Host "Dependencies installed." -ForegroundColor Green
    Write-Host ""
}

$style = [System.Diagnostics.ProcessWindowStyle]::$WindowStyle

$backendArgs = @("-Port", $BackendPort, "-Workers", $BackendWorkers)
$frontendArgs = @("-Port", $FrontendPort)

Write-Host "Launching backend and frontend (check the two PowerShell windows for logs)..." -ForegroundColor Cyan

$backend = Start-ServiceWindow `
    -ScriptPath $backendScript `
    -WorkingDirectory $backendDir `
    -ExtraArgs $backendArgs `
    -Style $style

Start-Sleep -Seconds 2

$frontend = Start-ServiceWindow `
    -ScriptPath $frontendScript `
    -WorkingDirectory $frontendDir `
    -ExtraArgs $frontendArgs `
    -Style $style

foreach ($proc in @($backend, $frontend)) {
    try {
        $proc.PriorityClass = [System.Diagnostics.ProcessPriorityClass]::BelowNormal
    } catch {
        # Harmless on some Windows builds / process types.
    }
}

Write-Host ""
Write-Host "Waiting for services to come online (up to ${StartupTimeoutSec}s)..." -ForegroundColor Cyan

$apiReady = Wait-ForPort -Port $BackendPort -Label "API" -TimeoutSec $StartupTimeoutSec
$uiReady = Wait-ForPort -Port $FrontendPort -Label "Frontend" -TimeoutSec $StartupTimeoutSec

Write-Host ""
if ($apiReady -and $uiReady) {
    Write-Host "Ready!" -ForegroundColor Green
    Write-Host "  Open UI:  http://127.0.0.1:$FrontendPort" -ForegroundColor Green
    Write-Host "  Open API: http://127.0.0.1:$BackendPort/docs" -ForegroundColor Green
    $lanScript = Join-Path $Root "scripts\show-lan-urls.ps1"
    if (Test-Path $lanScript) {
        Write-Host ""
        & $lanScript -FrontendPort $FrontendPort -ApiPort $BackendPort
    }
} else {
    Write-Host "Startup incomplete:" -ForegroundColor Red
    if (-not $apiReady) {
        Write-Host "  - API not listening on port $BackendPort (see backend PowerShell window)" -ForegroundColor Red
    }
    if (-not $uiReady) {
        Write-Host "  - Frontend not listening on port $FrontendPort (see frontend PowerShell window)" -ForegroundColor Red
    }
    Write-Host ""
    Write-Host "Tip: run .\start-project.ps1 -Install if dependencies are missing." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Launcher PIDs: backend shell $($backend.Id), frontend shell $($frontend.Id)" -ForegroundColor DarkGray
Write-Host "Stop with: .\stop-project.ps1 -CloseShellWindows" -ForegroundColor DarkGray
