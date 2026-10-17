@echo off
setlocal
echo ========================================================
echo Starting ExamRadar India - Backend Server (FastAPI)
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

echo Initializing API server on http://127.0.0.1:8000 ...
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Backend process terminated with exit code %ERRORLEVEL%.
    echo Check the error message above. If dependencies are missing, run:
    echo   pip install -r requirements.txt
    echo.
)
pause
