@echo off
cd /d "%~dp0.."
echo [GBT] 停止本机指挥官引擎（只停本仓起的那个 pid）
".\pyembed\python.exe" -X utf8 -c "import sys;sys.path.insert(0,r'%CD%');from gbt_allinone.tentacle import commander as C;print(C.stop())"
echo.
pause
