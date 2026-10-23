@echo off
setlocal
title GBT Xiao Tu Dou V8 - Full Panel (browser)
cd /d "%~dp0.."

REM ---------------------------------------------------------------
REM Why: the desktop shell launcher is a 420x780 transparent
REM pet window -- its first screen is mostly the avatar stage, so the
REM capability catalog / video studio / observer blocks sit far below.
REM The FULL panel is just the same local page in a normal browser.
REM This script makes sure the panel is up, then opens it full size.
REM
REM ASCII-only on purpose (cmd reads .bat as ANSI/GBK).
REM ---------------------------------------------------------------

set "PY="
if exist "C:\Python310\python.exe" set "PY=C:\Python310\python.exe"
if not defined PY if exist "C:\Python312\python.exe" set "PY=C:\Python312\python.exe"
if not defined PY where python >nul 2>nul && set "PY=python"

if not defined PY (
  echo [ERROR] Python was not found.
  pause
  exit /b 1
)

netstat -ano | findstr ":8765" | findstr LISTENING >nul
if errorlevel 1 (
  echo [1/2] starting the local panel on 127.0.0.1:8765 ...
  start "GBT Holo Panel" /min "%PY%" "holo_pet\launch_panel.py" --host 127.0.0.1 --port 8765
  timeout /t 6 /nobreak >nul
) else (
  echo [1/2] panel already listening on 127.0.0.1:8765
)

echo [2/2] opening the FULL panel in your default browser ...
start "" "http://127.0.0.1:8765/"
