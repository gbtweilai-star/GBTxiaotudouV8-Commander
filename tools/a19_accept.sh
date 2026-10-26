#!/bin/sh
# a19_accept —— 容器一起来，一条命令跑完全部验收（手册第 1 节的自动化版）
#
#   ① 容器状态与规格
#   ② 身份自述（她真答一句，原话 + tok/s，并落盘）
#   ③ prefill 阶梯 → 「45 秒窗口能吃多少 token」
#   ④ 能不能把本框整个切过去（三道闸）
#
# 退出码：0 全通 · 2 容器不在（其余步骤无意义，立刻停，不空跑）
set -u
cd "$(dirname "$0")" || exit 2

say() { printf '\n=== %s ===\n' "$1"; }

say "① 容器"
python3 a19_ctl.py status || { echo "容器不在 —— 后面三步都无意义，停。"; exit 2; }

say "② 身份自述（她真答一句）"
python3 her.py "用一句话说清：你是谁、谁开发的、谁守护的。" || exit 3

say "③ prefill 阶梯（窗口预算）"
python3 a19_prefill.py --window 45 || echo "（阶梯没跑通，预算按保守值走）"

say "④ 能不能切"
python3 a19_switch.py

say "账本（页面 + 本框共用）"
python3 her.py --tail 6
python3 her.py --sensor 5

exit 0
