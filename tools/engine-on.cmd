@echo off
cd /d "%~dp0.."
echo [GBT] 启动本机指挥官引擎（llama-server @127.0.0.1:8792）
".\pyembed\python.exe" -X utf8 -c "import sys,pathlib;sys.path.insert(0,r'%CD%');from gbt_allinone.tentacle import commander as C;print(C.start(wait=180))"
echo.
pause
