@echo off
rem ============================================================
rem  GBT小土豆V8 · 起本机自训权重引擎（她自己的口 :8111）
rem  用 vendor\llama\llama-server.exe 直接加载 state\weights 的 GGUF
rem  不起 python、不装依赖 —— 纯 llama.cpp 原生二进制
rem ============================================================
chcp 65001 >nul
setlocal enableextensions
cd /d "%~dp0..\.."

set "MODEL=state\weights\gbt-v8-v82-q5_0.gguf"
set "ENGINE=vendor\llama\llama-server.exe"
set "PORT=8111"
set "CTX=8192"
set "THREADS=12"
set "NGL=0"

if not exist "%MODEL%"  ( echo [x] 缺权重：%MODEL%   & pause & exit /b 2 )
if not exist "%ENGINE%" ( echo [x] 缺引擎：%ENGINE%  & pause & exit /b 2 )

rem 已经活着就直接复用，不重复起第二个进程
curl -s -o nul -w "" http://127.0.0.1:%PORT%/health --max-time 2 2>nul
if not errorlevel 1 (
  echo [=] :%PORT% 已在服务，直接复用
  exit /b 0
)

echo [.] 加载权重（4.88 GB · 首次约 10-40 秒）...
start "GBT-local-8111" /min "%ENGINE%" -m "%MODEL%" ^
  --host 127.0.0.1 --port %PORT% ^
  -c %CTX% -t %THREADS% -ngl %NGL% ^
  --alias gbt-v8-v82-q5_0 ^
  --no-context-shift --no-webui

set /a _n=0
:poll
curl -s -o nul -w "" http://127.0.0.1:%PORT%/health --max-time 2 2>nul
if not errorlevel 1 (
  echo [ok] http://127.0.0.1:%PORT%  ·  model=gbt-v8-v82-q5_0  ·  ctx=%CTX% threads=%THREADS% ngl=%NGL%
  exit /b 0
)
set /a _n+=1
if %_n% geq 90 ( echo [x] 180 秒没起来，看窗口 "GBT-local-8111" 的日志 & pause & exit /b 3 )
timeout /t 2 >nul
goto poll
