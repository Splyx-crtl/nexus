@echo off
REM ==========================================================
REM  NEXUS // TERMINAL - launcher (Windows)
REM  Creates a local virtual environment on first run,
REM  installs the dependencies and starts the game.
REM ==========================================================
setlocal
cd /d "%~dp0"
title NEXUS // TERMINAL

if not exist ".venv\Scripts\python.exe" (
    echo [NEXUS] First start: creating virtual environment...
    where py >nul 2>nul
    if %errorlevel%==0 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if not exist ".venv\Scripts\python.exe" (
        echo [NEXUS] ERROR: Python 3.12 or newer was not found. Install it from python.org and try again.
        pause
        exit /b 1
    )
    echo [NEXUS] Installing dependencies ^(this happens only once^)...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo [NEXUS] ERROR: dependency installation failed.
        pause
        exit /b 1
    )
)

".venv\Scripts\python.exe" main.py %*
if errorlevel 1 (
    echo.
    echo [NEXUS] The game exited with an error. See saves\error.log for details.
    pause
)
endlocal
