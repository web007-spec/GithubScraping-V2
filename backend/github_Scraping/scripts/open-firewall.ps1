# Allow inbound TCP 8000 (FastAPI management API) for extension + admin LAN access.
# Run as Administrator on the SERVER PC.

$ErrorActionPreference = "Stop"
$port = 8000
$ruleName = "GitHub Scraper Management API ($port)"

$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Firewall rule already exists: $ruleName" -ForegroundColor Yellow
} else {
    New-NetFirewallRule `
        -DisplayName $ruleName `
        -Direction Inbound `
        -Action Allow `
        -Protocol TCP `
        -LocalPort $port `
        -Profile Private, Domain | Out-Null
    Write-Host "Created firewall rule: $ruleName (TCP $port, Private + Domain)" -ForegroundColor Green
}

Write-Host "Test from another PC: http://YOUR-SERVER-IP:${port}/extension/ping" -ForegroundColor Cyan
