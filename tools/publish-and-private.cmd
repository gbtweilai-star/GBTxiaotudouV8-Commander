@echo off
cd /d "%~dp0.."
echo [GBT] 发布：推装修 + 设私人 + 设描述/话题
echo.
"..\pyembed\python.exe" -X utf8 "tools\publish-and-private.py" --prompt
echo.
pause
