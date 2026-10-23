@echo off
setlocal
title GBT Xiao Tu Dou V8 - Restart Panel
cd /d "%~dp0.."

REM ---------------------------------------------------------------
REM One-click restart: stop the panel that is already serving 8765,
REM then start a fresh one (so newly changed code actually takes effect).
REM
REM Why this file exists: the original launcher always spawns a NEW panel
REM process, but launch_panel.py reuses an already-running 8765 server --
REM so without stopping the old one first, new code never loads.
REM
REM ASCII-only on purpose: cmd.exe reads .bat as ANSI/GBK, and a UTF-8
REM Chinese literal here would be garbled and break the script
REM (pit list item #2: entry scripts must survive the console codepage).
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

echo [1/3] Stopping the old panel on 127.0.0.1:8765 ...
set "KILLED="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8765" ^| findstr LISTENING') do (
  taskkill /f /pid %%p >nul 2>nul && set "KILLED=1"
)
if defined KILLED (echo       stopped.) else (echo       nothing was listening.)
timeout /t 2 /nobreak >nul

echo [2/3] Starting the new panel ...
start "GBT Holo Panel" /min "%PY%" "holo_pet\launch_panel.py" --host 127.0.0.1 --port 8765
timeout /t 3 /nobreak >nul

echo [3/3] Opening the desktop shell ...
pushd "%~dp0"
call npx --no-install electron "desktop\main.cjs"
popd

if errorlevel 1 (
  echo.
  echo [HINT] Electron runtime missing. Run:  cd holo_pet ^&^& npm install --no-audit --no-fund electron@43.0.0
  pause
)
