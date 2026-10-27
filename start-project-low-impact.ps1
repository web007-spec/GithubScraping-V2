# Back-compat wrapper — use start-project.ps1
param(
    [switch]$Install,
    [int]$FrontendPort = 3001,
    [int]$BackendPort = 8000,
    [int]$BackendWorkers = 1
)

& (Join-Path $PSScriptRoot "start-project.ps1") `
    -Install:$Install `
    -FrontendPort $FrontendPort `
    -BackendPort $BackendPort `
    -BackendWorkers $BackendWorkers `
    -WindowStyle Normal
