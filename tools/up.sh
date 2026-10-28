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

# 🔴 2026-10-28：原来只判端口。端口一时没起来（进程还在启动 / 刚崩还没被回收）
#   就会**再起一个**，旧的还在 ⇒ 实测 panel_server 堆到 7 个、http.server 2 个，
#   把可用内存吃到只剩 259MB/4GB，然后 :8790 的 asyncio 进程被静默杀掉
#   （没有 Traceback，是 SIGKILL）—— 这就是它反复掉线的真原因。
#   现在：端口通 **或** 进程在，都算"已在跑"，绝不重复拉起。
# 🔴 2026-10-28：**不能用 pgrep** —— 实测在 iSH 上不可靠（`pgrep -c python3`
#   返回过 0，明明有 14 个）。于是 upm 的"已在跑"判断一直失效，
#   panel_server 被反复拉起 8 个，各自吃内存，可用内存掉到 85MB/4GB，
#   然后 :8790 的 asyncio 进程被内核 SIGKILL。
#   改用 ps + grep 判断，可靠。
upm() { ps -o args 2>/dev/null | grep -v grep | grep -qF -- "$1"; }
running() { up "$1" || upm "$2"; }

start_flr() {
  if running 3001 "dist/index.js"; then say ":3001 免费模型池" "✅ 已在跑"; return; fi
  [ -f "$FLR/server/dist/index.js" ] || { say ":3001 免费模型池" "🔴 缺 dist"; return; }
  cd "$FLR/server" || return
  FREEAPI_DB_DRIVER=node FREEAPI_DB_NO_WAL=1 IMAGE_NORMALIZE=off \
    setsid nohup node dist/index.js > "$LOG/flr.log" 2>&1 < /dev/null &
  cd "$BASE" || return
  if $PB wait 3001 130 >/dev/null 2>&1; then say ":3001 免费模型池" "✅ 已就绪"
  else say ":3001 免费模型池" "🔴 130s 未起 → logs/flr.log"; fi
}

start_page() {
  if running 8080 "http.server 8080"; then say ":8080 她的界面" "✅ 已在跑"; return; fi
  cd "$BASE" || return
  setsid nohup python3 -m http.server 8080 --bind 127.0.0.1 > "$LOG/page.log" 2>&1 < /dev/null &
  if $PB wait 8080 20 >/dev/null 2>&1; then say ":8080 她的界面" "✅ 已就绪"
  else say ":8080 她的界面" "🔴 未起"; fi
}

start_bridge() {
  if running 8791 "model_bridge.py"; then say ":8791 模型桥" "✅ 已在跑"; return; fi
  pkill -f 'model_bridge.py' 2>/dev/null; sleep 1
  cd "$BASE" || return
  # 🔴 2026-10-28 主人口径：A19 不在时也要能答（可用性优先）。
  #   GBT_ALLOW_CLOUD_FALLBACK=1 是框架留的正规开关；降级后回包照旧如实标
  #   lane / weights_ours=false，可审计，不冒充自有权重。
  GBT_ALLOW_CLOUD_FALLBACK=1 \
    setsid nohup python3 -u runtime/model_bridge.py --port 8791 > "$LOG/bridge.log" 2>&1 < /dev/null &
  if $PB wait 8791 30 >/dev/null 2>&1; then say ":8791 模型桥" "✅ 已就绪"
  else say ":8791 模型桥" "🔴 未起 → logs/bridge.log"; fi
}

start_index() {
  if running 8792 "index_daemon.py"; then say ":8792 索引层" "✅ 已在跑"; return; fi
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
  if running 8765 "panel_server.py"; then say ":8765 面板后端" "✅ 已在跑"; return; fi
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
  if running 8790 "async_gate.py"; then say ":8790 asyncio 批量车道" "✅ 已在跑"; return; fi
  pkill -f async_gate.py 2>/dev/null; sleep 1
  cd "$BASE" || return
  setsid nohup python3 -u runtime/async_gate.py --port 8790 > "$LOG/async_gate.log" 2>&1 < /dev/null &
  if $PB wait 8790 40 >/dev/null 2>&1; then say ":8790 asyncio 批量车道" "✅ 已就绪"
  else say ":8790 asyncio 批量车道" "🔴 未起 → logs/async_gate.log"; fi
}

start_patrol() {
  # 低频真实巡检（每 5 分钟一轮）——**故意不隔离**，观测要进生产账。
  # 只调只读零作用域的位，不制造 gate_denied 噪声。
  # 作用：让 duty_board 的判据有干净的真实数据，不再全靠探活填。
  if pgrep -f duty_patrol.py >/dev/null 2>&1; then say ":巡检 生产观测" "✅ 已在跑"; return; fi
  cd "$BASE" || return
  setsid nohup python3 -u tools/duty_patrol.py --interval 5 > "$LOG/patrol.out" 2>&1 < /dev/null &
  sleep 2
  if pgrep -f duty_patrol.py >/dev/null 2>&1; then say ":巡检 生产观测" "✅ 已启动（每 5 分钟）"
  else say ":巡检 生产观测" "🔴 起不来"; fi
}

start_mem() {
  # 记忆统一层：建索引 + 喂框架自己的索引层（只喂有出处的）
  python3 tools/memory_unify.py --index > /dev/null 2>&1 || true
  local OUT
  OUT=$(python3 - <<'PY2'
import sys, json
sys.path.insert(0, "tools")
import memory_unify as M
M.index()
st = M.stats()
fv = M.feed_vault()
fed = len([x for x in fv.get("fed") or [] if x.get("ok")])
skip = len(fv.get("skipped") or [])
print("%d|%d|%d" % (st.get("total") or 0, fed, skip))
PY2
)
  local TOT FED SKP
  TOT=${OUT%%|*}; FED=$(echo "$OUT" | cut -d'|' -f2); SKP=$(echo "$OUT" | cut -d'|' -f3)
  python3 - "$TOT" "$FED" "$SKP" <<'PY3'
import sys
t, f, s = sys.argv[1], sys.argv[2], sys.argv[3]
print("    %-22s \u2705 \u7d22\u5f15 %s \u6761 \u00b7 \u5582\u5e93 %s%s"
      % (":MEM \u8bb0\u5fc6\u7edf\u4e00\u5c42", t, f,
         ("\uff08\u8df3\u8fc7 %s \u6761\u65e0\u51fa\u5904\uff09" % s) if int(s) else ""))
PY3
}


start_dhgate() {
  # 数字人上场前必过的一道门（八条资产闸 · 只读）
  # 🔴 2026-10-28：dh_asset_gate 原来是孤儿 —— run_task 叫得到，没一条活路径用它。
  #   接上后第一次跑就发现：闸写死 joints==65，在役件 dh-v7-detail.glb 是 66 ⇒ 对在役件恒红。
  local OUT="$BASE/logs/dh_preflight.json"
  python3 tools/dh_preflight.py > "$OUT" 2>/dev/null || true
  if grep -q '"ok": true' "$OUT" 2>/dev/null; then
    printf "    %-22s ✅ 八条全绿（%s）\n" ":DHGATE 资产闸" "$(grep -o 'dh-[a-z0-9.-]*\.glb' "$OUT" | head -1)"
  else
    printf "    %-22s ⚠ 有红项，见 logs/dh_preflight.json\n" ":DHGATE 资产闸"
  fi
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
  # 🔴 2026-10-28：免费池（node，9~17 个进程）默认**不起** —— 它是内存大户，
  #   起来会把可用内存吃到 259MB/4GB，导致 :8790 被静默杀掉。
  #   桥的降级链已改成 deepseek 优先（0.8s、几乎不吃内存）。
  #   真要 259 个免费模型时：FORCE_FLR=1 sh tools/up.sh up
  if [ "${FORCE_FLR:-0}" = "1" ]; then start_flr; else say ":3001 免费模型池" "⏭ 默认不起（内存优先，要它用 FORCE_FLR=1）"; fi
  start_mem; start_dhgate; start_page; start_bridge; start_gate; start_panel; start_index; start_patrol; start_sentinel; probe_a19
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
  for row in "8080|http.server 8080" "8791|model_bridge.py" "8790|async_gate.py" "8792|index_daemon.py" "8765|panel_server.py" "3001|dist/index.js" "patrol|duty_patrol.py"; do
    pat=${row#*|}
    if pkill -f "$pat" 2>/dev/null; then say ":${row%%|*}" "已停"; else say ":${row%%|*}" "本来没跑"; fi
  done
  ;;
*)
  echo "用法: sh tools/up.sh up|status|down"
  ;;
esac
