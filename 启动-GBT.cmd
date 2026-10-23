@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  GBT小土豆V8 · 一键启动（自有权重链路）
echo ============================================

echo [1/4] 启动本机权重服务 :8792 ...
start "" /min "C:\Python312\python.exe" "tools\model-bridge\local_llm_server.py" --model "state\weights\gbt-v8-v82-q5_0.gguf" --port 8792 --ctx 256 --threads 8
timeout /t 6 >nul

echo [2/4] 启动模型桥 :8791 ...
set GBT_ENABLE_SELFHOST_LANE=1
set GBT_OURS_BASE_URL=http://127.0.0.1:8792/v1
start "" /min py -3.14 -X utf8 "tools\model-bridge\server.py" --port 8791
timeout /t 4 >nul

echo [3/4] 体检 ...
"C:\Python312\python.exe" "tools\model-bridge\doctor.py"
echo.
echo [4/4] 启动桌面壳 ...
pushd holo_pet_w3
start "" ".\node_modules\.bin\electron.cmd" .
popd

echo.
echo 完成。壳里的「模型对话」页默认走 selfhost（本机 Q5_0）。
echo 需要逐条真答体验检时，单独跑：doctor.py --chat
pause
