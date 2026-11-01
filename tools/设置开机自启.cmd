@echo off

setlocal enableextensions

cd /d "%~dp0"

echo GBT小土豆V8 · 安装「认知界面服务」登录自启

echo.

set "DST=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\GBT-console.cmd"

copy /y "%~dp0autostart\GBT-console.cmd" "%DST%" >nul

if errorlevel 1 (

  echo [失败] 拷贝到 Startup 失败，请手动复制 tools\autostart\GBT-console.cmd 到：

  echo        %DST%

  pause

  exit /b 1

)

echo [完成] 已装：%DST%

echo 下次登录自动起服务；本次可先跑一次 启动-GBT.cmd 或 python tools\console-server.py --port 8766

echo 取消：删掉上面的 GBT-console.cmd 即可。

pause

