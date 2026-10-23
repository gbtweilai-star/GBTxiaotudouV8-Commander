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
import re
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


BAKE_MARK = ROOT / "state" / "bake-pages.json"
BAKE_EVERY_S = 6 * 3600      # 重烤节奏：6 小时一次（判定阈值是 24 小时，留 4 倍余量）
BAKE_GEN = ROOT / "tools" / "codex-scripts" / "bake-all-pages.py"
BRAIN_GEN = ROOT / "tools" / "codex-scripts" / "brain-feed.py"
BRAIN_OUT = "holo_pet_w3/brain/brain-data.js"
BRAIN_DATA = ROOT / "holo_pet_w3" / "brain" / "brain-data.js"
# 🔴 2026-10-22 加（F19 的驱动）：满载红灯猎手此前只有「手动跑一次」的入口 ——
#    按 P8「修复件没接上驱动 = 没修」，把它接进本循环：**24 小时跑一次**（4 负载 × 3 轮，
#    比手跑轻），红了把失败用例名逐条写进 `state/load-red-hunt.json`（猎手自己负责写）。
HUNT_MARK = ROOT / "state" / "load-red-hunt.json"
HUNT_GEN = ROOT / "tools" / "codex-scripts" / "load-red-hunt.py"
HUNT_EVERY_S = 24 * 3600


def _brain_at():
    """主脑数据里那个 `at`（判"到底刷新了没有"用；不看 rc）。"""
    try:
        head = BRAIN_DATA.read_text(encoding="utf-8", errors="replace")[:400]
    except OSError:
        return None
    m = re.search(r'"at":"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"', head)
    return m.group(1) if m else None


def _maybe_bake() -> dict:
    """**P8 驱动**：把「快照页/主脑数据会自己变旧」接上常驻驱动，而不是靠人记得跑。

    为什么加（2026-10-22 实测）：`bake-all-pages.py` 早就写好了、判据也立了（快照页 >24h 就黄），
    但**没有任何东西会来调它** —— 开机自检里 `每一页都绑到触手` 就一直带着
    「energy 烤的是 40.8 小时前」这类警告。这正是本仓 P8：修复件写完 ≠ 修好，驱动方没改就是没修。

    🔴 2026-10-22 自纠（P20 同型，第一次真跑才抓到）：`brain-feed.py` **不给 `--out` 就根本不落盘**
       —— 它 rc=0 并自己在末尾喊「本次没有落盘」。我第一版只判 `rc==0`，于是驱动"成功"了而主脑
       还是 41 小时前的。现口径：① 必须带 `--out`；② 判"写没写"看**数据里的 `at`**，不看退出码。
    口径：6 小时一次（判定线 24 小时的 1/4），失败如实记进心跳、不静默。
    """
    import subprocess
    now = time.time()
    try:
        old = json.loads(BAKE_MARK.read_text(encoding="utf-8")) if BAKE_MARK.is_file() else {}
    except (ValueError, OSError):
        old = {}
    age = now - float(old.get("ts") or 0)
    if old and age < BAKE_EVERY_S:
        return {"skipped": True, "age_s": round(age), "next_in_s": round(BAKE_EVERY_S - age),
                "brain_at": _brain_at()}
    rec = {"ts": now, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "steps": []}
    brain_before = _brain_at()
    steps = (
        ("brain-feed", BRAIN_GEN, ["--out", BRAIN_OUT]),
        ("bake-all-pages", BAKE_GEN, []),
    )
    for name, script, extra in steps:
        if not script.is_file():
            rec["steps"].append({"step": name, "ok": False, "why": "脚本不在：%s" % script})
            continue
        t0 = time.time()
        try:
            r = subprocess.run([sys.executable, "-X", "utf8", str(script)] + extra,
                               cwd=str(ROOT), capture_output=True, timeout=1800)
            stdout = (r.stdout or b"").decode("utf-8", "replace")
            item = {"step": name, "rc": r.returncode, "ok": r.returncode == 0,
                    "ms": round((time.time() - t0) * 1000),
                    "tail": stdout.strip().splitlines()[-1:] or [""]}
            if name == "brain-feed":
                # 判"真写了没有"：at 变了才算（不认 rc，不认"脚本说成功"）
                after = _brain_at()
                item["brain_at"] = after
                item["ok"] = bool(item["ok"] and after and after != brain_before)
                if item.get("ok") is False and after == brain_before:
                    item["why"] = "at 没变（%s）⇒ 这次没有真落盘" % after
            rec["steps"].append(item)
        except Exception as e:                      # noqa: BLE001
            rec["steps"].append({"step": name, "ok": False, "why": "%s: %s" % (type(e).__name__, e)})
    rec["brain_at"] = _brain_at()
    BAKE_MARK.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    print("[monitor-loop] 重烤：%s · 主脑 at=%s" % (" · ".join(
        "%s=%s" % (s["step"], "ok" if s.get("ok") else "🔴" + str(s.get("rc") or s.get("why")))
        for s in rec["steps"]), rec.get("brain_at")), flush=True)
    return {"skipped": False, "steps": rec["steps"], "brain_at": rec.get("brain_at")}


def _maybe_hunt() -> dict:
    """**P8 驱动**：把「满载红灯猎手」接上常驻循环（F19）。

    为什么加：猎手（`load-red-hunt.py`）能把「复现不出来的假红」变成**有回执的复现尝试**，
    并逐条留下失败用例名；但在这之前**没有任何东西会来调它** —— 跑一次就躺在回执里，
    过几天又变成"没人记得跑"。这正是本仓 P8。

    口径：
      · 24 小时一次（F19 是观察型，不需要更密）；
      · 负载 4 进程 × 3 轮（比手跑的 5 轮轻，够触发负载相关假红）；
      · 判"跑成功"看**回执里的 `at` 变没变**（不看 rc —— 猎手本身红/绿都 rc=0，
        它把结论写进 `reproduced` 字段，那才是读数）。
    """
    import subprocess
    now = time.time()
    try:
        old = json.loads(HUNT_MARK.read_text(encoding="utf-8")) if HUNT_MARK.is_file() else {}
    except (ValueError, OSError):
        old = {}
    try:
        old_ts = time.mktime(time.strptime(str(old.get("at") or "")[:19], "%Y-%m-%dT%H:%M:%S"))
    except (ValueError, OSError):
        old_ts = 0
    age = now - old_ts if old_ts else 1e9
    if old_ts and age < HUNT_EVERY_S:
        return {"skipped": True, "age_s": round(age), "next_in_s": round(HUNT_EVERY_S - age),
                "reproduced": old.get("reproduced"), "at": old.get("at")}
    if not HUNT_GEN.is_file():
        return {"skipped": False, "ok": False, "why": "猎手不在：%s" % HUNT_GEN}
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", str(HUNT_GEN),
                            "--runs", "3", "--load", "4"],
                           cwd=str(ROOT), capture_output=True, timeout=3600)
        rc = r.returncode
        tail = ((r.stdout or b"") + (r.stderr or b"")).decode("utf-8", "replace").strip().splitlines()[-2:]
    except Exception as e:                      # noqa: BLE001
        return {"skipped": False, "ok": False, "why": "%s: %s" % (type(e).__name__, e)}
    after = {}
    try:
        after = json.loads(HUNT_MARK.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        after = {}
    fresh = bool(after.get("at")) and str(after.get("at")) != str(old.get("at") or "")
    return {"skipped": False, "ok": bool(fresh), "rc": rc,
            "ms": round((time.time() - t0) * 1000),
            "at": after.get("at"), "reproduced": after.get("reproduced"),
            "failure_names": (after.get("failure_names") or [])[:5],
            "why": None if fresh else "回执 at 没变（这次没有真跑成）",
            "tail": tail}


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
    # 🔴 2026-10-22 加：把「重烤」也记进心跳（否则"有没有人烤过"从心跳里看不出来）
    try:
        rec["bake"] = _maybe_bake()
    except Exception as e:                          # noqa: BLE001
        rec["bake"] = {"skipped": False, "error": "%s: %s" % (type(e).__name__, e)}
    # 🔴 2026-10-22 加：把「满载红灯猎手」也记进心跳（F19 的驱动）
    try:
        rec["hunt"] = _maybe_hunt()
    except Exception as e:                          # noqa: BLE001
        rec["hunt"] = {"skipped": False, "error": "%s: %s" % (type(e).__name__, e)}
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
