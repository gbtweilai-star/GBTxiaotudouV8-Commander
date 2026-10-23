@echo off
title GBT Xiao Tu Dou V8 - 3D Digital Human
cd /d "%~dp0.."
set "PY="
call :probe "C:\Python310\python.exe"
call :probe python
call :probe py -3
call :probe "C:\Python312\python.exe"
if not defined PY (
  echo [ERROR] Python was not found.
  echo.
  pause
  exit /b 1
)
echo Using Python: %PY%
echo Panel URL: http://127.0.0.1:8765/
echo Close this window to stop the panel.
echo.
%PY% "holo_pet\launch_panel.py" --host 127.0.0.1 --port 8765
pause

:probe
if defined PY goto :eof
"%~1" %~2 -c "import encodings, sys" >nul 2>nul
if errorlevel 1 goto :eof
set "PY="%~1" %~2"
goto :eof
