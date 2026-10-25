#!/bin/sh
# 一键起「她」—— 三个件 + 自检
#   1) 她的本体界面   :8080  (holo_pet_w3, 718 页 + 3D 全身)
#   2) 模型桥         :8791  (runtime/model_bridge.py, 上游 selfhost → A19)
#   3) 索引常驻层     :8792  (tools/index_daemon.py, 亚毫秒查)
#
# 用法：
#   sh tools/start-her.sh          起全部（已在跑的会跳过）
#   sh tools/start-her.sh status   只看状态
#   sh tools/start-her.sh stop     全停
set -u
R="$(cd "$(dirname "$0")/.." && pwd)"
cd "$R" || exit 1

ok() { timeout 6 curl -s -m 4 -o /dev/null -w "%{http_code}" "$1" 2>/dev/null; }
up() { [ "$(ok "$1")" = "200" ]; }

start_http() {
  up http://127.0.0.1:8080/ && { echo "  ⏭ 她的界面 8080 已在跑"; return; }
  pkill -f "http.server 8080" 2>/dev/null
  ( cd "$R/holo_pet_w3" && setsid nohup python3 -m http.server 8080 --bind 127.0.0.1 >/tmp/holo.log 2>&1 & )
  i=0; while [ $i -lt 10 ]; do sleep 1; up http://127.0.0.1:8080/ && break; i=$((i+1)); done
  up http://127.0.0.1:8080/ && echo "  ✅ 她的界面 :8080" || echo "  🔴 她的界面起不来，看 /tmp/holo.log"
}

start_bridge() {
  up http://127.0.0.1:8791/health && { echo "  ⏭ 模型桥 8791 已在跑"; return; }
  pkill -f "model_bridge" 2>/dev/null
  setsid nohup python3 -u runtime/model_bridge.py --port 8791 >/tmp/bridge.log 2>&1 &
  i=0; while [ $i -lt 10 ]; do sleep 1; up http://127.0.0.1:8791/health && break; i=$((i+1)); done
  up http://127.0.0.1:8791/health && echo "  ✅ 模型桥 :8791" || echo "  🔴 模型桥起不来，看 /tmp/bridge.log"
}

start_idx() {
  up http://127.0.0.1:8792/ping && { echo "  ⏭ 索引常驻 8792 已在跑"; return; }
  pkill -f "index_daemon.py serve" 2>/dev/null
  setsid nohup python3 -u tools/index_daemon.py serve --port 8792 >/tmp/idx.log 2>&1 &
  i=0; while [ $i -lt 16 ]; do sleep 2; up http://127.0.0.1:8792/ping && break; i=$((i+1)); done
  up http://127.0.0.1:8792/ping && echo "  ✅ 索引常驻 :8792" || echo "  🔴 索引起不来，看 /tmp/idx.log"
}

status() {
  echo "── 三件状态 ──"
  printf "  她的界面 :8080  %s\n" "$(ok http://127.0.0.1:8080/)"
  printf "  模型桥   :8791  %s\n" "$(ok http://127.0.0.1:8791/health)"
  printf "  索引常驻 :8792  %s\n" "$(ok http://127.0.0.1:8792/ping)"
  echo "── A19（LM Pocket，需要 App 在前台）──"
  printf "  A19      :1234  %s\n" "$(ok http://127.0.0.1:1234/v1/models)"
  echo
  echo "── 桥看见的车道 ──"
  timeout 10 curl -s -m 8 http://127.0.0.1:8791/health 2>/dev/null | python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print('  默认上游:', d.get('default'))
    for u in d.get('upstreams',[]):
        mark = '✅' if u.get('key_ready') else '·'
        print('   %s %-10s %s' % (mark, u['name'], u['base_url']))
except Exception:
    print('  （桥没起）')
"
}

case "${1:-start}" in
  status) status ;;
  stop)
    pkill -f "http.server 8080" 2>/dev/null
    pkill -f model_bridge 2>/dev/null
    pkill -f "index_daemon.py serve" 2>/dev/null
    echo "  已全停" ;;
  *)
    echo "══ 起她 ══"
    start_http; start_bridge; start_idx
    echo
    status
    echo
    echo "══ 下一步 ══"
    echo "  1) 打开 LM Pocket → Load & Start Server（A19 才有算力）"
    echo "  2) 浏览器开 http://127.0.0.1:8080/index.html → 分享 → 添加到主屏幕"
    ;;
esac
