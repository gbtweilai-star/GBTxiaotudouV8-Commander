# -*- coding: utf-8 -*-
"""monitor-loop.py —— 多域监控的**常驻循环**（一次启动，自己每 5 分钟一拍，直到进程被杀）。

为什么改成常驻（2026-10-19 实测留痕）：
先前用 Windows 任务计划「每 N 分钟拉起 monitor-once.py」，实测两次都没按点跑：
- `schtasks /Create /SC MINUTE` 版的 Last Result = **-2147024629（0x8007010B = ERROR_DIRECTORY）**
  —— 命令行带引号被任务计划拼坏了；
- 重建成 XML 后 Next Run Time 停在 8:40 不动，Last Run 不刷新。
与其继续和任务计划的引号/触发器搏斗，改成：**常驻进程自己 sleep 循环**（进程内状态，不依赖引号），
任务计划只留一条 `ONLOGON` 负责开机把它拉起来（不负责每 N 分钟）。

一拍做：`sched_tick`（把到期调度跑掉）→ 写心跳 `state/monitor-loop.json` → sleep。
单实例：`state/monitor-loop.lock` 里记 pid，发现前一个还活着就直接退出（不叠进程）。

用法：
  py -3.14 tools/codex-scripts/monitor-loop.py            # 常驻（前台，Ctrl+C 停）
  py -3.14 tools/codex-scripts/monitor-loop.py --once     # 只跑一拍就退
  py -3.14 tools/codex-scripts/monitor-loop.py --interval 300
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
LOCK = ROOT / "state" / "monitor-loop.lock"
INTERVAL = 300


def _alive(pid: int) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _claim_lock() -> bool:
    if LOCK.is_file():
        try:
            old = int(json.loads(LOCK.read_text(encoding="utf-8")).get("pid") or 0)
        except (ValueError, OSError):
            old = 0
        if old and old != os.getpid() and _alive(old):
            return False
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    LOCK.write_text(json.dumps({"pid": os.getpid(),
                                "at": time.strftime("%Y-%m-%dT%H:%M:%S")},
                               ensure_ascii=False), encoding="utf-8")
    return True


def _tick() -> int:
    t0 = time.time()
    ran, err = [], None
    try:
        from gbt_allinone import api as _api
        body = _api.run_task("sched_tick", {})
        for _ in range(6):                          # 剥信封
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
    except Exception as e:                          # noqa: BLE001
        err = "%s: %s" % (type(e).__name__, e)

    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ts": round(t0, 3),
           "duration_ms": round((time.time() - t0) * 1000, 1), "pid": os.getpid(),
           "mode": "resident",
           "ran": [{"schedule": r.get("schedule"), "workflow": r.get("workflow"),
                    "status": r.get("status")} for r in ran],
           "count": len(ran), "error": err}
    HEART.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    bad = [r for r in ran if str(r.get("status")) != "ok"]
    print("[monitor-loop] %s · ran=%d · %.0f ms%s"
          % (rec["at"], rec["count"], rec["duration_ms"],
             (" · 🔴 " + (err or "调度失败 %s" % bad)) if (err or bad) else " · ok"),
          flush=True)
    return 1 if (err or bad) else 0


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    once = "--once" in args
    interval = INTERVAL
    if "--interval" in args:
        i = args.index("--interval")
        if i + 1 < len(args):
            try:
                interval = max(30, int(args[i + 1]))
            except ValueError:
                pass
    if not _claim_lock():
        print("[monitor-loop] 已有实例在跑（见 %s）—— 本进程退出" % LOCK.name)
        return 0
    if once:
        return _tick()
    print("[monitor-loop] 常驻启动 pid=%d · 每 %d 秒一拍（Ctrl+C 停）" % (os.getpid(), interval),
          flush=True)
    while True:
        try:
            _tick()
        except Exception as e:                      # noqa: BLE001
            print("[monitor-loop] 这一拍炸了：%s: %s" % (type(e).__name__, e), flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
