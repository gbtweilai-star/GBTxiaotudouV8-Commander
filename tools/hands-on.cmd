@echo off
cd /d "%~dp0"
echo [GBT] 万能插·手服务启动中（127.0.0.1:8791）...
echo 保持此窗口开着；关掉=手停。
"..\pyembed\python.exe" -X utf8 "tools\gbt-hands.py"
pause
