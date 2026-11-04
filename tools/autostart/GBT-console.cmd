@echo off
rem GBT小土豆V8 · 认知界面服务 :8766 登录自启（删掉 Startup 里的同名文件即取消）
rem 走 console_service.start：幂等、写状态 pid、服务进程无窗口、日志落 state\console-server.log
chcp 65001 >nul
cd /d "%~dp0..\.."
"pyembed\python.exe" -X utf8 "gbt_allinone\console_service.py" start >> "state\console-server.log" 2>&1
