@echo off
cd /d "%~dp0"
echo [GBT] GitHub 仓库整理（先预览，再确认）
echo.
"..\pyembed\python.exe" -X utf8 "tools\github-repo-clean.py" --prompt --apply
echo.
pause
