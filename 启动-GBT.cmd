@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  GBT小土豆V8 · 一键启动（自有权重链路）
echo ============================================

call :probe 8792
if "%UP%"=="1" (
  echo [1/4] 权重服务 :8792 已在运行，跳过
) else (
  echo [1/2] 启动权重服务 :8792 ...
  start "" /min "C:\Python312\python.exe" "tools\model-bridge\local_llm_server.py" --model "state\weights\gbt-v8-v82-q5_0.gguf" --port 8792 --ctx 256 --threads 8
  call :wait 8792 60
)

call :probe 8791
if "%UP%"=="1" (
  echo [2/4] 模型桥 :8791 已在运行，跳过
) else (
  echo [2/2] 启动模型桥 :8791 ...
  set GBT_ENABLE_SELFHOST_LANE=1
  set GBT_OURS_BASE_URL=http://127.0.0.1:8792/v1
  start "" /min py -3.14 -X utf8 "tools\model-bridge\server.py" --port 8791
  call :wait 8791 30
)

echo [3/4] 体检 ...
"C:\Python312\python.exe" "tools\model-bridge\doctor.py"
echo.

echo [4/4] 启动桌面壳 ...
if "%~1"=="--no-shell" (
  echo   已跳过（--no-shell）
) else (
  pushd holo_pet_w3
  start "" ".\node_modules\.bin\electron.cmd" .
  popd
)

echo.
echo 完成。壳里的「模型对话」页默认走 selfhost（本机 Q5_0）。
echo 逐条真答体验检：doctor.py --chat
pause
exit /b 0

:probe
set UP=0
for /f %%c in ('curl -s -o nul -w "%%{http_code}" http://127.0.0.1:%~1/health 2^>nul') do if "%%c"=="200" set UP=1
exit /b 0

:wait
set /a _n=0
:waitloop
call :probe %~1
if "%UP%"=="1" exit /b 0
set /a _n+=1
if %_n% geq %~2 (
  echo   [警告] %~1 等 %~2 秒仍未就绪
  exit /b 1
)
timeout /t 2 >nul
goto waitloop
