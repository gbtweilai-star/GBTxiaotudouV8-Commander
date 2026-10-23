@echo off
setlocal
title GBT Xiao Tu Dou V8 - Holographic Panel
cd /d "%~dp0.."

set "PY="
if exist "C:\Python310\python.exe" set "PY=C:\Python310\python.exe"
if not defined PY if exist "C:\Python312\python.exe" set "PY=C:\Python312\python.exe"
if not defined PY where python >nul 2>nul && set "PY=python"

if not defined PY (
  echo [ERROR] Python was not found.
  pause
  exit /b 1
)

echo Using Python: %PY%
echo The launcher reuses an existing GBT panel on the same port.
echo.
"%PY%" "holo_pet\launch_panel.py" --host 127.0.0.1 --port 8765
pause
