#!/bin/sh
# 双击或在终端执行：起本地服务，然后打开 index.html
cd "$(dirname "$0")" && python3 -m http.server 8099 &
sleep 1
echo "打开 http://127.0.0.1:8099/index.html"
python3 -c "import webbrowser;webbrowser.open('http://127.0.0.1:8099/index.html')" 2>/dev/null || true
wait
