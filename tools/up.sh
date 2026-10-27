#!/bin/sh
# GBT小土豆V8 · 五路链路幂等启动器
#   sh tools/up.sh up|status|down|her
#
# 链路：:8080 她的界面 → :8791 模型桥 → :1234 A19(LM Pocket)
#      :3001 免费模型池 · :8792 索引层
#
# ── 踩过的坑，改之前先读 ──────────────────────────────
# ① 不用 curl 探活：iSH 的 curl 对 node 起的服务秒回 000（其实活着且回 200），
#    实测 :3001 被误判成"停了"好几次。一律走 tools/svcprobe.py 的 socket 探测。
# ② 不用固定 sleep：node 在 iSH 走 --no-opt 解释执行，冷启约 50 秒。
#    固定等 12 秒必然假红，改成 wait 轮询。
# ③ 后台进程必须三重重定向（>log 2>&1 </dev/null），否则父 shell 一退就 SIGPIPE。
# ④ 必须 setsid 脱离会话，否则被 shell 退出连带杀掉。
# ⑤ :1234 是另一个 App（LM Pocket），iSH 起不了，只能 apple-open 唤醒；
#    iOS 一切后台约 50 秒回收，属正常现象，不是故障。

BASE=/var/minis/shared/gbtv8
FLR=/var/minis/shared/flrouter
LOG=$BASE/logs
PB="python3 $BASE/tools/svcprobe.py"
mkdir -p "$LOG"

say() { printf '  %-26s %s\n' "$1" "$2"; }
up()  { $PB tcp "$1" >/dev/null 2>&1; }

start_flr() {
  if up 3001; then say ":3001 免费模型池" "✅ 已在跑"; return; fi
  [ -f "$FLR/server/dist/index.js" ] || { say ":3001 免费模型池" "🔴 缺 dist"; return; }
  cd "$FLR/server" || return
  FREEAPI_DB_DRIVER=node FREEAPI_DB_NO_WAL=1 IMAGE_NORMALIZE=off \
    setsid nohup node dist/index.js > "$LOG/flr.log" 2>&1 < /dev/null &
  cd "$BASE" || return
  if $PB wait 3001 130 >/dev/null 2>&1; then say ":3001 免费模型池" "✅ 已就绪"
  else say ":3001 免费模型池" "🔴 130s 未起 → logs/flr.log"; fi
}

start_page() {
  if up 8080; then say ":8080 她的界面" "✅ 已在跑"; return; fi
  cd "$BASE" || return
  setsid nohup python3 -m http.server 8080 --bind 127.0.0.1 > "$LOG/page.log" 2>&1 < /dev/null &
  if $PB wait 8080 20 >/dev/null 2>&1; then say ":8080 她的界面" "✅ 已就绪"
  else say ":8080 她的界面" "🔴 未起"; fi
}

start_bridge() {
  if up 8791; then say ":8791 模型桥" "✅ 已在跑"; return; fi
  pkill -f 'model_bridge.py' 2>/dev/null; sleep 1
  cd "$BASE" || return
  setsid nohup python3 -u runtime/model_bridge.py --port 8791 > "$LOG/bridge.log" 2>&1 < /dev/null &
  if $PB wait 8791 30 >/dev/null 2>&1; then say ":8791 模型桥" "✅ 已就绪"
  else say ":8791 模型桥" "🔴 未起 → logs/bridge.log"; fi
}

start_index() {
  if up 8792; then say ":8792 索引层" "✅ 已在跑"; return; fi
  pkill -f 'index_daemon.py' 2>/dev/null; sleep 1
  cd "$BASE" || return
  setsid nohup python3 -u tools/index_daemon.py serve --port 8792 > "$LOG/index.log" 2>&1 < /dev/null &
  if $PB wait 8792 45 >/dev/null 2>&1; then say ":8792 索引层" "✅ 已就绪"
  else say ":8792 索引层" "🔴 未起 → logs/index.log"; fi
}

start_panel() {
  # 面板后端 :8765 —— 生产面板的读数与 /api/mirror 都靠它。
  # 它原来因为 research_status/social_platforms 从未发布而一行都起不来，
  # 已改成可缺省（缺了就如实报 unimplemented）。
  if up 8765; then say ":8765 面板后端" "✅ 已在跑"; return; fi
  pkill -f panel_server.py 2>/dev/null; sleep 1
  cd "$BASE" || return
  setsid nohup python3 -u holo_pet/panel_server.py --port 8765 > "$LOG/panel.log" 2>&1 < /dev/null &
  if $PB wait 8765 40 >/dev/null 2>&1; then say ":8765 面板后端" "✅ 已就绪"
  else say ":8765 面板后端" "🔴 未起 → logs/panel.log"; fi
}

start_gate() {
  # asyncio 单进程桥（:8790）——**批量车道**
  #   同步桥 :8791 是 thread-per-request，单进程 512 路就顶天；
  #   这个单进程实测 4096 路零失败（无连接线程）。
  #   页面仍走 :8791（它要用 /v1/dispatch /v1/route /warm，asyncio 版没实现那些）。
  if up 8790; then say ":8790 asyncio 批量车道" "✅ 已在跑"; return; fi
  pkill -f async_gate.py 2>/dev/null; sleep 1
  cd "$BASE" || return
  setsid nohup python3 -u runtime/async_gate.py --port 8790 > "$LOG/async_gate.log" 2>&1 < /dev/null &
  if $PB wait 8790 40 >/dev/null 2>&1; then say ":8790 asyncio 批量车道" "✅ 已就绪"
  else say ":8790 asyncio 批量车道" "🔴 未起 → logs/async_gate.log"; fi
}

start_sentinel() {
  # A19 哨兵：每 5 秒探 :1234，一出现就自动验收（模型名 / 首字 / tok/s / 身份）
  # 并落 state/a19_ready.json。**不需要改桥配置** —— 桥默认上游本来就是 selfhost。
  if pgrep -f a19_attach.py >/dev/null 2>&1; then say ":1234 哨兵" "✅ 已在跑"; return; fi
  cd "$BASE" || return
  setsid nohup python3 -u tools/a19_attach.py > "$LOG/a19_attach.out" 2>&1 < /dev/null &
  sleep 2
  if pgrep -f a19_attach.py >/dev/null 2>&1; then say ":1234 哨兵" "✅ 已启动（每 5s 探一次）"
  else say ":1234 哨兵" "🔴 起不来"; fi
}

probe_a19() {
  if up 1234; then say ":1234 A19" "✅ 在线"; return; fi
  command -v apple-open >/dev/null 2>&1 && apple-open lmpocket:// >/dev/null 2>&1
  if $PB wait 1234 20 >/dev/null 2>&1; then say ":1234 A19" "✅ 已唤醒"
  else say ":1234 A19" "⚠ 离线（正常：打开 LM Pocket 即用，后台 50s 被回收）"; fi
}

case "${1:-status}" in
up)
  echo "=== 拉齐五路 ==="
  start_page; start_bridge; start_gate; start_panel; start_index; start_flr; start_sentinel; probe_a19
  echo; echo "  她: http://127.0.0.1:8080/index.html"
  ;;
status)
  echo "=== 链路状态 ==="
  for row in "3001|免费模型池" "8080|她的界面" "8791|模型桥(同步)" "8790|批量车道(asyncio)" "8765|面板后端" "8792|索引层" "1234|A19"; do
    p=${row%%|*}; n=${row#*|}
    if up "$p"; then say ":$p $n" "✅ up"
    else
      case "$p" in
        1234) if [ -f "$BASE/state/a19_ready.json" ] && grep -q '"ok": true' "$BASE/state/a19_ready.json" 2>/dev/null; then
                say ":$p $n" "✅ 已验证就绪（$(python3 -c "import json;d=json.load(open('$BASE/state/a19_ready.json'));print('%.2fs %s tok/s'%(d.get('elapsed_s') or 0,d.get('tok_per_s')))" 2>/dev/null)）"
              else
                say ":$p $n" "⚠ 离线（哨兵在等，出现即自动接入）"
              fi ;;
        *)    say ":$p $n" "🔴 down" ;;
      esac
    fi
  done
  echo
  echo "=== HTTP 实测 ==="
  $PB http 8080 /index.html
  $PB http 8791 /health
  $PB http 8790 /health
  $PB http 8765 /api/state
  $PB http 8792 /health
  $PB http 3001 /api/ping
  ;;
down)
  echo "=== 停止（A19 由 App 自管）==="
  for row in "8080|http.server 8080" "8791|model_bridge.py" "8790|async_gate.py" "8792|index_daemon.py" "8765|panel_server.py" "3001|dist/index.js"; do
    pat=${row#*|}
    if pkill -f "$pat" 2>/dev/null; then say ":${row%%|*}" "已停"; else say ":${row%%|*}" "本来没跑"; fi
  done
  ;;
*)
  echo "用法: sh tools/up.sh up|status|down"
  ;;
esac
