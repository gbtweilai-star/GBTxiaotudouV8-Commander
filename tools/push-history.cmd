@echo off
cd /d "%~dp0.."
echo [GBT] 强推重写后的历史（方案A 最后一步）
echo.
"..\pyembed\python.exe" -X utf8 "tools\push-rewritten-history.py" --prompt
echo.
pause
