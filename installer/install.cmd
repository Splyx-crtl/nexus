@echo off
rem Launcher used inside the self-extracting NEXUS-Setup.exe
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1" %*
