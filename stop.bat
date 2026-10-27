@echo off
setlocal
cd /d "%~dp0"

title Outreach Console - Stopping
echo.
echo Stopping Outreach Console (API + Frontend)...
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop-project.ps1" -CloseShellWindows

echo.
echo Optional: stop portable MongoDB on port 27017?
choice /C YN /M "Stop MongoDB too"
if errorlevel 2 goto done
if errorlevel 1 (
  for /f "tokens=5" %%P in ('netstat -ano ^| findstr ":27017" ^| findstr "LISTENING"') do (
    echo Stopping PID %%P on port 27017...
    taskkill /PID %%P /F >nul 2>&1
  )
)

:done
echo.
echo Done.
pause
endlocal
