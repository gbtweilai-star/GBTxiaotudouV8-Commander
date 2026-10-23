@echo off
REM ══ GBT小土豆V8 · 原生 n8n 控制台 ══
REM 我们自己的 n8n：本机自托管 · 数据全在 ~/.n8n · 与框架能力网关直连
REM 用法：n8n-ctl start | stop | status | log
setlocal
set N8N_PORT=5678
set N8N_SECURE_COOKIE=false
if "%~1"=="start" (
  echo [GBT] 启动原生 n8n（端口 %N8N_PORT%）...
  if "%GBT_GATEWAY_TOKEN%"=="" echo [警告] GBT_GATEWAY_TOKEN 未设 —— 桥接工作流会 401（先 setx GBT_GATEWAY_TOKEN ^<值^>）
  start "GBT-n8n" /MIN cmd /c "n8n start > "%USERPROFILE%\.n8n\n8n-server.log" 2>&1"
  echo [GBT] 已拉起，日志：%USERPROFILE%\.n8n\n8n-server.log
  echo [GBT] 面板：http://127.0.0.1:%N8N_PORT% （首次访问建管理员账号）
  goto :eof
)
if "%~1"=="stop" (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%N8N_PORT% ^| findstr LISTENING') do (
    taskkill /F /PID %%a >nul 2>&1 && echo [GBT] 已停止 PID %%a
  )
  goto :eof
)
if "%~1"=="status" (
  curl -s -m 5 -o nul -w "n8n: HTTP %%{http_code}\n" http://127.0.0.1:%N8N_PORT%/
  curl -s -m 5 -o nul -w "能力网关: HTTP %%{http_code}\n" http://127.0.0.1:31717/health
  goto :eof
)
if "%~1"=="log" (
  powershell -NoProfile -Command "Get-Content -Tail 30 '%USERPROFILE%\.n8n\n8n-server.log'"
  goto :eof
)
echo 用法: n8n-ctl start ^| stop ^| status ^| log
echo.
echo 本实例归属：GBT小土豆V8 框架（自托管，数据在 %%USERPROFILE%%\.n8n）
echo 桥接工作流导入：n8n import:workflow --input="C:\Users\ADMIN\Desktop\GBT小土豆V8\config\n8n-gbt-bridge.json"
endlocal
