# start-servo.cmd —— 从 Medium 上下文拉起常驻伺服（双击或由 shell 调用）
@echo off
setlocal
set PS1=C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8\tools\rtservo\rtservo-daemon.ps1
start "" /min powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%PS1%" -Port 7791
endlocal
