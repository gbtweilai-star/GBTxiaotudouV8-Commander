# -*- coding: utf-8 -*-
"""monitor-once.py —— 多域监控的**心跳发条**（一次 = 一拍）。

为什么要有这一件（2026-10-19 补齐闭环）：
`impact-monitor-tick.py` 是"驱动轮"，但它自己也得有人来转。仓里 `schedule.run_forever`
**没有任何调用方**（这个洞已经留痕过一次）——所以真正让它 24/7 转起来的方式是：
**Windows 任务计划每 2 分钟拉起本件一次**，不需要一个常驻进程被谁看着。

一拍做三件事：
1. `sched_tick` —— 把到期调度（impact_monitor 每小时 / truth-sched / persona-evolve）真跑掉；
2. 打一次心跳到 `state/monitor-loop.json`（`at` / `ran` / `duration_ms` / `pid`）；
3. 退出码：这一拍有调度报错 ⇒ 1（任务计划里能看到"上次结果"）。

⚠️ 它**不打印长篇**（任务计划里没人看）：回执只写文件，命令行只留一行。
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    if hasattr(_s, "reconfigure"):
        _s.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HEART = ROOT / "state" / "monitor-loop.json"


def main() -> int:
    t0 = time.time()
    ran, err = [], None
    try:
        from gbt_allinone import api as _api
        env = _api.run_task("sched_tick", {})
        body = env
        for _ in range(6):
            if not isinstance(body, dict):
                break
            if any(k in body for k in ("gate", "gbt_stamp", "ok_source", "kind", "stamp")) \
                    and isinstance(body.get("result"), dict):
                body = body["result"]
                continue
            break
        ran = (body or {}).get("ran") or []
        if "ran" not in (body or {}):
            err = "回执里没有 ran：%s" % sorted(body or {})[:8]
    except Exception as e:                                    # noqa: BLE001
        err = "%s: %s" % (type(e).__name__, e)

    rec = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ts": round(t0, 3),
        "duration_ms": round((time.time() - t0) * 1000, 1),
        "pid": os.getpid(),
        "ran": [{"schedule": r.get("schedule"), "workflow": r.get("workflow"),
                 "status": r.get("status")} for r in ran],
        "count": len(ran),
        "error": err,
    }
    HEART.parent.mkdir(parents=True, exist_ok=True)
    HEART.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")

    bad = [r for r in ran if str(r.get("status")) != "ok"]
    print("[monitor-once] %s · ran=%d · %.0f ms%s"
          % (rec["at"], rec["count"], rec["duration_ms"],
             (" · 🔴 " + (err or "调度失败 " + str(bad))) if (err or bad) else " · ok"))
    return 1 if (err or bad) else 0


if __name__ == "__main__":
    raise SystemExit(main())
