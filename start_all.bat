@echo off
REM Doble clic para iniciar TODO el entorno de Content Factory.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_all.ps1"
pause
