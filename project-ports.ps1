# Shared port cleanup helpers for Outreach Console (Windows).
$ErrorActionPreference = "Continue"

function Get-PortListenerPids {
    param([int]$Port)

    $pids = [System.Collections.Generic.HashSet[int]]::new()
    $connections = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
    foreach ($connection in $connections) {
        $processId = [int]$connection.OwningProcess
        if ($processId -gt 0) {
            [void]$pids.Add($processId)
        }
    }

    if ($pids.Count -eq 0) {
        $matches = netstat -ano -p tcp 2>$null |
            Select-String -Pattern "^\s*TCP\s+[^\s]+:$Port\s+[^\s]+\s+LISTENING\s+(\d+)\s*$"
        foreach ($match in $matches) {
            $processId = [int]$match.Matches[0].Groups[1].Value
            if ($processId -gt 0) {
                [void]$pids.Add($processId)
            }
        }
    }

    return @($pids)
}

function Get-LivePortListenerPids {
    param([int]$Port)

    $live = @()
    foreach ($processId in (Get-PortListenerPids -Port $Port)) {
        if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
            $live += $processId
        }
    }
    return $live
}

function Test-PortListening {
    param([int]$Port)
    return (Get-LivePortListenerPids -Port $Port).Count -gt 0
}

function Wait-PortFree {
    param(
        [int]$Port,
        [int]$TimeoutSec = 20
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (-not (Test-PortListening -Port $Port)) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return -not (Test-PortListening -Port $Port)
}

function Stop-ProjectProcessesByCommandLine {
    param([string[]]$Patterns)

    $names = @("python.exe", "python3.exe", "py.exe", "node.exe")
    foreach ($name in $names) {
        $processes = Get-CimInstance Win32_Process -Filter "Name = '$name'" -ErrorAction SilentlyContinue
        foreach ($proc in $processes) {
            $cmd = [string]$proc.CommandLine
            if (-not $cmd) {
                continue
            }
            foreach ($pattern in $Patterns) {
                if ($cmd -match $pattern) {
                    Write-Host "Stopping $name PID $($proc.ProcessId) ($pattern)" -ForegroundColor Yellow
                    Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
                    break
                }
            }
        }
    }
}

function Stop-LauncherShellWindows {
    $patterns = @(
        "start-api\.ps1",
        "start-frontend\.ps1",
        "uvicorn app\.main:app",
        "next\\dist\\bin\\next"
    )

    $shells = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -in @("powershell.exe", "pwsh.exe") }

    foreach ($shell in $shells) {
        $cmd = [string]$shell.CommandLine
        if (-not $cmd) {
            continue
        }
        $isLauncher = $false
        foreach ($pattern in $patterns) {
            if ($cmd -match $pattern) {
                $isLauncher = $true
                break
            }
        }
        if (-not $isLauncher) {
            continue
        }
        Write-Host "Closing launcher shell PID $($shell.ProcessId)" -ForegroundColor Yellow
        Stop-Process -Id $shell.ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Test-ProjectProcess {
    param([System.Diagnostics.Process]$Process)

    $name = $Process.ProcessName.ToLowerInvariant()
    if ($name -match "^(node|python|python3|py)$") {
        return $true
    }
    if ($name -eq "powershell" -or $name -eq "pwsh") {
        try {
            $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($Process.Id)" -ErrorAction SilentlyContinue).CommandLine
            if ($cmd -match "start-api\.ps1|start-frontend\.ps1|uvicorn app\.main:app|next\\dist\\bin\\next") {
                return $true
            }
        } catch {
            return $false
        }
    }
    return $false
}

function Stop-ProcessTree {
    param([int]$ProcessId)

    if ($ProcessId -le 0) {
        return
    }

    $children = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.ParentProcessId -eq $ProcessId }

    foreach ($child in $children) {
        Stop-ProcessTree -ProcessId $child.ProcessId
    }

    Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
}

function Stop-ProjectServers {
    param(
        [int[]]$Ports = @(3001, 8000),
        [switch]$CloseShellWindows,
        [switch]$Quiet
    )

    if ($CloseShellWindows) {
        Stop-LauncherShellWindows
        Start-Sleep -Milliseconds 800
    }

    Stop-ProjectProcessesByCommandLine @(
        "uvicorn app\.main:app",
        "-m uvicorn app\.main:app",
        "multiprocessing\.spawn import spawn_main",
        "next\\dist\\bin\\next(\.js)? dev"
    )

    $stoppedCount = 0
    $seenPids = @{}

    foreach ($Port in ($Ports | Select-Object -Unique)) {
        foreach ($processId in (Get-LivePortListenerPids -Port $Port)) {
            if ($seenPids.ContainsKey($processId)) {
                continue
            }
            $seenPids[$processId] = $true

            $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
            if (-not $process) {
                continue
            }

            if (-not (Test-ProjectProcess -Process $process)) {
                if (-not $Quiet) {
                    Write-Host "Port $Port is used by $($process.ProcessName) PID $processId (not stopped)." -ForegroundColor DarkYellow
                }
                continue
            }

            if (-not $Quiet) {
                Write-Host "Stopping $($process.ProcessName) PID $processId on port $Port" -ForegroundColor Yellow
            }
            Stop-ProcessTree -ProcessId $processId
            $stoppedCount++
        }
    }

    foreach ($Port in ($Ports | Select-Object -Unique)) {
        [void](Wait-PortBindable -Port $Port -TimeoutSec 8)
    }

    return $stoppedCount
}

function Test-PortBindable {
    param([int]$Port)

    $code = @"
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind(('0.0.0.0', $Port))
    print('ok')
except OSError:
    print('busy')
finally:
    s.close()
"@
    $result = python -c $code 2>$null
    return "$result".Trim() -eq "ok"
}

function Wait-PortBindable {
    param(
        [int]$Port,
        [int]$TimeoutSec = 20
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-PortBindable -Port $Port) {
            return $true
        }
        Start-Sleep -Milliseconds 500
    }
    return (Test-PortBindable -Port $Port)
}

function Ensure-ProjectPortsFree {
    param(
        [int[]]$Ports = @(8000),
        [switch]$CloseShellWindows
    )

    [void](Stop-ProjectServers -Ports $Ports -CloseShellWindows:$CloseShellWindows -Quiet)

    $blocked = @()
    foreach ($Port in ($Ports | Select-Object -Unique)) {
        if (-not (Test-PortBindable -Port $Port)) {
            $blocked += $Port
        }
    }

    if ($blocked.Count -gt 0) {
        Write-Host ""
        Write-Host "Port(s) still in use: $($blocked -join ', ')" -ForegroundColor Red
        foreach ($Port in $blocked) {
            foreach ($processId in (Get-LivePortListenerPids -Port $Port)) {
                $process = Get-Process -Id $processId -ErrorAction SilentlyContinue
                if ($process) {
                    Write-Host "  Port $Port -> $($process.ProcessName) PID $processId" -ForegroundColor Red
                }
            }
        }
        Write-Host "Run from repo root: .\stop-project.ps1 -CloseShellWindows" -ForegroundColor Yellow
        return $false
    }

    return $true
}
