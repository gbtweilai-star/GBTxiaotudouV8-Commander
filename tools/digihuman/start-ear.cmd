@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在起「耳朵」（本机离线中文识别桥，只监听 127.0.0.1:8770）...
"C:\Users\ADMIN\AppData\Roaming\uv\python\cpython-3.14.0-windows-x86_64-none\python.exe" tools\digihuman\ear-server.py --port 8770
pause
