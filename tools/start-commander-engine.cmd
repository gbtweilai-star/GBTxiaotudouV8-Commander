@echo off
REM 二代本机指挥官引擎（llama-server · Q5_0 主道 · 127.0.0.1:8792）
REM 由启动文件夹的 GBT-CommanderEngine.vbs 在登录时拉起。
REM 权重: state\weights\gbt-v8-v82-q5_0.gguf（sha256 983f19a6...c0fcd262f）
cd /d "C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8\vendor\llama"
start "" /b "C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8\vendor\llama\llama-server.exe" ^
  --model "C:\Users\Lenovo E14 Gen 5\Desktop\GBT小土豆V8\state\weights\gbt-v8-v82-q5_0.gguf" ^
  --port 8792 --ctx-size 32768 --threads 12 --host 127.0.0.1
