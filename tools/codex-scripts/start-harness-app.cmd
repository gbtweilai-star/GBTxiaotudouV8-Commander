@echo off
rem start-harness-app.cmd - double-click launcher for the DeepSeek Harness desktop app.
rem Runs start-harness-app.ps1: clears window-less instances (they keep the single-instance
rem lock, so a plain double-click exits with code 0 and looks like "flashes then closes"),
rem then launches one copy and verifies the window.
rem ASCII-only on purpose (cmd.exe reads .cmd in the OEM code page).
setlocal
set "PS1=%~dp0start-harness-app.ps1"
if not exist "%PS1%" (
  echo [ERR] missing: %PS1%
  pause
  exit /b 2
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%PS1%"
if errorlevel 1 pause
endlocal
