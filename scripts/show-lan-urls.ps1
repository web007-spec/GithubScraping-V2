# Print URLs other PCs on your network should use
param([int]$FrontendPort = 3001, [int]$ApiPort = 8000)

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
    Where-Object { $_.IPAddress -notlike "127.*" -and $_.PrefixOrigin -ne "WellKnown" } |
    Select-Object -First 1 -ExpandProperty IPAddress)

if (-not $ip) {
    $ip = "YOUR_LAN_IP"
}

Write-Host ""
Write-Host "=== Outreach Console — LAN server URLs ===" -ForegroundColor Cyan
Write-Host "Your LAN IP: $ip"
Write-Host ""
Write-Host 'On THIS PC (server):' -ForegroundColor Yellow
Write-Host "  API:      http://${ip}:${ApiPort}"
Write-Host "  Frontend: http://${ip}:${FrontendPort}"
Write-Host "  Local:    http://localhost:${FrontendPort}"
Write-Host ""
Write-Host "On OTHER PCs — open in browser:" -ForegroundColor Yellow
Write-Host "  http://${ip}:${FrontendPort}"
Write-Host ""
Write-Host "frontend/.env (optional, for explicit HMR allowlist):" -ForegroundColor Green
Write-Host "  DEV_ALLOWED_ORIGINS=${ip},${ip}:${FrontendPort}"
Write-Host ""
Write-Host "LAN clients connect directly to the API on port ${ApiPort} (no extra config)." -ForegroundColor Green
Write-Host "  Restart the frontend after changing frontend/.env" -ForegroundColor DarkGray
Write-Host ""
Write-Host "backend/github_Scraping/.env CORS_ORIGINS should include:" -ForegroundColor Green
Write-Host "  http://localhost:${FrontendPort},http://${ip}:${FrontendPort}"
Write-Host ""
Write-Host "Windows Firewall: allow inbound TCP ${FrontendPort} and ${ApiPort}" -ForegroundColor Magenta
Write-Host ""
