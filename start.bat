@echo off
setlocal
cd /d "%~dp0"

title Outreach Console - Starting
echo.
echo ========================================
echo   Outreach Console - starting...
echo ========================================
echo.

REM Bypass local PowerShell script restrictions for this run only.
set "PS=powershell.exe -NoProfile -ExecutionPolicy Bypass"

echo [1/3] Starting MongoDB...
%PS% -File "%~dp0start-mongo.ps1"
if errorlevel 1 (
  echo.
  echo MongoDB failed to start. Fix that first, then run start.bat again.
  echo.
  pause
  exit /b 1
)

echo.
echo [2/3] Applying Mongo schema if needed...
python "%~dp0scripts\apply_mongodb_schema.py"
if errorlevel 1 (
  echo Schema apply failed - continuing anyway if DB was already set up.
)

echo.
echo [3/3] Starting API + Frontend...
%PS% -File "%~dp0start-project.ps1"
if errorlevel 1 (
  echo.
  echo Project start failed. Check the messages above.
  echo.
  pause
  exit /b 1
)

echo.
echo ========================================
echo   Ready
echo   UI:  http://127.0.0.1:3001
echo   API: http://127.0.0.1:8000/docs
echo ========================================
echo.
echo Tip: double-click stop.bat to shut everything down.
echo.
pause
endlocal
