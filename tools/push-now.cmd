@echo off
cd /d "%~dp0.."
echo [GBT] 全量同步到 GitHub（一次 clone + 一次 push）
echo.
"..\pyembed\python.exe" -X utf8 "tools\git-portable-sync.py" --prompt --apply
echo.
pause
