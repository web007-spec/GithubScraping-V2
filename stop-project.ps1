# Stop project-owned Node/Python processes that listen on the default ports.
param(
    [object[]]$Ports = @(3001, 8000),
    [switch]$CloseShellWindows
)

$ErrorActionPreference = "Continue"

$PortList = @()
foreach ($Item in $Ports) {
    foreach ($Value in "$Item".Split(",")) {
        $Parsed = 0
        if ([int]::TryParse($Value.Trim(), [ref]$Parsed)) {
            $PortList += $Parsed
        }
    }
}
$PortList = @($PortList | Select-Object -Unique)

. (Join-Path $PSScriptRoot "project-ports.ps1")

$stoppedCount = Stop-ProjectServers -Ports $PortList -CloseShellWindows:$CloseShellWindows

foreach ($Port in $PortList) {
    if (Test-PortListening -Port $Port) {
        Write-Host "Port ${Port}: in use." -ForegroundColor DarkYellow
    } else {
        $stale = @(Get-PortListenerPids -Port $Port | Where-Object {
            -not (Get-Process -Id $_ -ErrorAction SilentlyContinue)
        })
        if ($stale.Count -gt 0) {
            Write-Host "Port ${Port}: free (ignoring stale socket entry)." -ForegroundColor DarkGray
        } else {
            Write-Host "Port ${Port}: free." -ForegroundColor DarkGray
        }
    }
}

if ($stoppedCount -gt 0) {
    Write-Host "Stopped $stoppedCount project process(es)." -ForegroundColor Green
} else {
    Write-Host "No project processes needed stopping on port(s): $($PortList -join ', ')." -ForegroundColor Cyan
}
