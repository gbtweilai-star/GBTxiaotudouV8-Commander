# -*- coding: utf-8 -*-
"""monitor-loop-health.py —— 判「多域监控的循环是不是真的还在转」。

为什么必需（2026-10-19）：`sched_define` 只是**登记**，`monitor-once.py` 只是**一拍**，
真正让它们 24/7 转起来的是 **Windows 任务计划 GBT-MonitorLoop（每 2 分钟）**。
任务被删/被停用/机器没开，在读数上和"一切正常"长得一模一样 —— 所以必须有这一条判据。

判据（非零退出 = 循环断了）：
- `state/monitor-loop.json` 不存在 ⇒ 红（从来没人拍过）
- 最后一拍距今 > 600 秒 ⇒ 红（任务没在跑，或机器刚起来还没到 2 分钟 —— 给 10 分钟宽限）
- 最后一拍 `error` 非空 ⇒ 红（把原因原话带出来）
- 任务计划里查不到 `GBT-MonitorLoop` ⇒ **报告但不判红**（可能换了调度方式），
  把"查不到"如实打出来，不许当"没问题"。

用法：py -3.14 tools/codex-scripts/monitor-loop-health.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
HEART = ROOT / "state" / "monitor-loop.json"
TASK = "GBT-MonitorLoop"
# 留痕（2026-10-19 实测）：任务原先设 2 分钟一拍，但**整点那一拍要跑完整工作流**
# （impact_monitor 三节点，含全仓 stat 的 drift ≈ 90–240 秒）⇒ 与下一拍重叠，任务计划
# 默认"不启动新实例"，于是心跳会出现 4 分钟以上的空档。改成 5 分钟一拍 + 阈值 900 秒，
# 既不重叠，也不会把"正在跑重活"误判成"循环断了"。
STALE_S = 900


def _task_state() -> str:
    try:
        r = subprocess.run(["schtasks", "/Query", "/TN", TASK, "/FO", "LIST"],
                           capture_output=True, text=True, timeout=20,
                           encoding="utf-8", errors="replace")
    except Exception as e:                                    # noqa: BLE001
        return "查不到（%s）" % type(e).__name__
    if r.returncode != 0:
        return "查不到（任务不存在或无权查询）"
    for line in (r.stdout or "").splitlines():
        if line.strip().startswith("Status"):
            return "任务在册 · " + line.strip()
    return "任务在册"


def main() -> int:
    if not HEART.is_file():
        print("🔴 循环从没跑过：没有 %s" % HEART.relative_to(ROOT))
        print("   装法：schtasks /Create /TN %s /SC MINUTE /MO 2 /TR \"<python> monitor-once.py\" /F"
              % TASK)
        return 1
    try:
        d = json.loads(HEART.read_text(encoding="utf-8"))
    except ValueError as e:
        print("🔴 心跳文件坏了：%s" % e)
        return 1
    age = time.time() - float(d.get("ts") or 0)
    print("心跳：%s（%.0f 秒前）· ran=%s · pid=%s · 用时 %s ms"
          % (d.get("at"), age, d.get("count"), d.get("pid"), d.get("duration_ms")))
    print("任务：%s" % _task_state())
    if d.get("error"):
        print("🔴 上一拍报错：%s" % d["error"])
        return 1
    if age > STALE_S:
        print("🔴 循环断了：最后一拍在 %.0f 秒前（阈值 %d）—— 任务被停/被删/机器刚起"
              % (age, STALE_S))
        return 1
    print("✅ 循环在转：常驻 monitor-loop 每 5 分钟一拍（上一拍 %.0f 秒前）｜开机由 %s 拉起"
          % (age, TASK))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
