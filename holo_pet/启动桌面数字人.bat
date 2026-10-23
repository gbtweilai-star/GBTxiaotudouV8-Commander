@echo off
setlocal
title GBT Xiao Tu Dou V8 - Desktop Digital Human
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

echo [1/2] Ensuring the local panel is running on 127.0.0.1:8765 ...
start "GBT Holo Panel" /min "%PY%" "holo_pet\launch_panel.py" --host 127.0.0.1 --port 8765
timeout /t 3 /nobreak >nul

rem [2/2] 桌面壳：**在役壳是 holo_pet_w3/shell/main.cjs**。
rem   2026-10-15 清旧：本目录原来的 desktop\main.cjs 与 holo_pet/package.json 的 main 都指向一个
rem   **不存在的目录**（Test-Path=False）——死指针不修，改指到在役壳；旧指针当场作废。
echo [2/2] Opening the transparent always-on-top desktop shell (holo_pet_w3) ...
pushd "%~dp0..\holo_pet_w3"
call npx --no-install electron "shell\main.cjs"
popd

if errorlevel 1 (
  echo.
  echo [HINT] Electron runtime missing. Run:  cd holo_pet_w3 ^&^& npm install --no-audit --no-fund electron@43.0.0
  pause
)
