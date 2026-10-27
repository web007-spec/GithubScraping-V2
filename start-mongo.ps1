# Start portable MongoDB for Outreach Console (local dev).
param(
    [int]$Port = 27017,
    [string]$BindIp = "127.0.0.1"
)

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$dest = Join-Path $Root ".tools\mongodb"
$mongodPathFile = Join-Path $dest "mongod.path"
$data = Join-Path $dest "data"
$log = Join-Path $dest "log\mongod.log"

function Test-MongoPort {
    param([int]$ListenPort)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $client.Connect("127.0.0.1", $ListenPort)
        $client.Close()
        return $true
    } catch {
        return $false
    }
}

if (Test-MongoPort -ListenPort $Port) {
    Write-Host "MongoDB already listening on ${BindIp}:${Port}" -ForegroundColor Green
    exit 0
}

if (-not (Test-Path $mongodPathFile)) {
    Write-Host "Portable MongoDB not found." -ForegroundColor Red
    Write-Host "Expected: $mongodPathFile" -ForegroundColor Yellow
    Write-Host "Install MongoDB Community, or extract mongodb-windows zip under .tools\mongodb and save mongod.exe path to mongod.path" -ForegroundColor Yellow
    exit 1
}

$mongod = (Get-Content $mongodPathFile -Raw).Trim()
if (-not (Test-Path $mongod)) {
    Write-Host "mongod.exe missing at: $mongod" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $data, (Split-Path $log) | Out-Null
Write-Host "Starting mongod on ${BindIp}:${Port} ..." -ForegroundColor Cyan
$proc = Start-Process -FilePath $mongod `
    -ArgumentList @("--dbpath", $data, "--bind_ip", $BindIp, "--port", "$Port", "--logpath", $log) `
    -PassThru -WindowStyle Hidden

$ok = $false
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Seconds 1
    if (Test-MongoPort -ListenPort $Port) {
        $ok = $true
        break
    }
}

if (-not $ok) {
    Write-Host "MongoDB failed to start. Log: $log" -ForegroundColor Red
    if (Test-Path $log) { Get-Content $log -Tail 30 }
    exit 1
}

Write-Host "MongoDB ready (PID $($proc.Id)) on ${BindIp}:${Port}" -ForegroundColor Green
Write-Host "Then: python scripts\apply_mongodb_schema.py" -ForegroundColor DarkGray
Write-Host "Then: .\start-project.ps1" -ForegroundColor DarkGray
