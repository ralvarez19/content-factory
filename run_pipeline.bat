@echo off
REM Doble clic para el flujo guiado: ideas -> guion -> video.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_pipeline.ps1"
pause
