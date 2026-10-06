@echo off
REM ==========================================================
REM  NEXUS // TERMINAL - build the Windows application
REM
REM  build_exe.bat              -> dist\NEXUS\NEXUS.exe
REM  build_exe.bat installer    -> additionally dist\NEXUS-Setup.exe
REM ==========================================================
setlocal
cd /d "%~dp0"
title NEXUS // TERMINAL - build

if not exist ".venv\Scripts\python.exe" (
    echo [BUILD] Creating virtual environment...
    where py >nul 2>nul
    if %errorlevel%==0 ( py -3 -m venv .venv ) else ( python -m venv .venv )
    if not exist ".venv\Scripts\python.exe" ( echo [BUILD] Python 3.12+ not found. & pause & exit /b 1 )
)

echo [BUILD] Installing build dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 ( echo [BUILD] dependency installation failed & pause & exit /b 1 )

echo [BUILD] Preparing icon and version resource...
".venv\Scripts\python.exe" tools\make_version_info.py
if errorlevel 1 ( echo [BUILD] version info failed & pause & exit /b 1 )

echo [BUILD] Running PyInstaller...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --windowed --name NEXUS ^
    --icon assets\nexus.ico ^
    --version-file build\version_info.txt ^
    --add-data "data;data" ^
    --add-data "missions;missions" ^
    --add-data "assets;assets" ^
    --add-data "ui\qml;ui\qml" ^
    --exclude-module tkinter ^
    main.py
if errorlevel 1 ( echo [BUILD] PyInstaller failed & pause & exit /b 1 )

if not exist "dist\NEXUS\saves" mkdir "dist\NEXUS\saves"
copy /y README.md "dist\NEXUS\README.md" >nul
copy /y LICENSE "dist\NEXUS\LICENSE.txt" >nul

echo.
echo [BUILD] Done: dist\NEXUS\NEXUS.exe
echo         Saves and settings are stored in dist\NEXUS\saves next to the executable.

if /i "%~1"=="installer" (
    echo [BUILD] Creating installer...
    powershell -NoProfile -ExecutionPolicy Bypass -File installer\build_installer.ps1
    if errorlevel 1 ( echo [BUILD] installer failed & pause & exit /b 1 )
) else (
    echo         Run "build_exe.bat installer" to also create dist\NEXUS-Setup.exe
)
if /i not "%~1"=="nopause" if /i not "%~2"=="nopause" pause
endlocal
