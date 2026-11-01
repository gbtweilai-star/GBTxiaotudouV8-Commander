@echo off
rem GBT小土豆V8 · 认知界面服务 :8766 登录自启（删掉 Startup 里的同名文件即取消）
cd /d "%~dp0..\.."
start "" /min "pyembed\python.exe" -X utf8 "tools\console-server.py" --port 8766
