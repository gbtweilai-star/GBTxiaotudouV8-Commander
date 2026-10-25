#!/bin/sh
# ============================================================
# GBT 验场 · 一个命令跑完全部判据
#   主人的口径：「绝不放过任何一位变化而不自知」
#
# 用法：
#   sh tools/verify.sh            复查（改完之后跑）
#   sh tools/verify.sh baseline   重拍基线（动手之前跑）
#   sh tools/verify.sh full       基线 + 复查（一条链路跑通）
#
# 退出码：0 全过 · 1 有断链或读数变了 · 2 环境缺件
# ============================================================
set -u
R=$(cd "$(dirname "$0")/.." && pwd)
cd "$R" || exit 2
MODE="${1:-check}"
FAIL=0

hr() { printf '%s\n' "──────────────────────────────────────────────────────────"; }

# ── 0. 前置：daemon 在不在（不在就如实说，不替它起）────────────
hr
printf '0) 环境\n'
if timeout 6 curl -s -m 4 -o /dev/null http://127.0.0.1:8792/ping 2>/dev/null; then
  printf '   常驻索引  ✅ 在跑\n'
else
  printf '   常驻索引  ⚠ 未起（daemon 相关判据会红）\n'
  printf '             起法：setsid nohup python3 -u tools/index_daemon.py serve --port 8792 >/tmp/idx.log 2>&1 &\n'
fi

# ── 1. 连接点 ─────────────────────────────────────────────
hr
printf '1) 连接点（谁依赖谁，改一处会不会坏一处）\n'
if timeout 280 python3 tools/conn_check.py; then
  printf '   → 连接点全通\n'
else
  printf '   → 🔴 有断链\n'; FAIL=1
fi

# ── 2. 探针 / 基线 ────────────────────────────────────────
hr
case "$MODE" in
  baseline|full)
    printf '2) 拍基线\n'
    timeout 280 python3 tools/monitor.py baseline || FAIL=1
    ;;
esac

if [ "$MODE" != "baseline" ]; then
  hr
  printf '2) 复查（逐位 diff）\n'
  if timeout 280 python3 tools/monitor.py check; then
    printf '   → 与基线逐位一致\n'
  else
    printf '   → 🔴 读数有变化\n'; FAIL=1
  fi
fi

# ── 3. 结论 ──────────────────────────────────────────────
hr
if [ "$FAIL" = "0" ]; then
  printf '结论：✅ 全部通过（%s）\n' "$(date '+%H:%M:%S')"
else
  printf '结论：🔴 有问题，逐条看上面\n'
fi
hr
exit "$FAIL"
