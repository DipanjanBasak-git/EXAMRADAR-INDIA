@echo off
setlocal
echo ========================================================
echo Starting ExamRadar India - Scheduled Discovery Worker
echo ========================================================
cd /d "%~dp0backend"

where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python 3 was not found in your system PATH.
    echo Please install Python 3.10+ and ensure "Add python.exe to PATH" is checked.
    echo.
    pause
    exit /b 1
)

echo Starting background discovery scheduler...
python -m app.workers.discovery_worker

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Discovery worker terminated with exit code %ERRORLEVEL%.
    echo Please check database access or logs.
    echo.
)
pause
