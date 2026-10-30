# -*- coding: utf-8 -*-
"""monitor-loop.py —— 多域监控的**常驻循环**（一次启动，自己每 5 分钟一拍，直到进程被杀）。

为什么改成常驻（2026-10-19 实测留痕）：
先前用 Windows 任务计划「每 N 分钟拉起 monitor-once.py」，实测两次都没按点跑：
- `schtasks /Create /SC MINUTE` 版的 Last Result = **-2147024629（0x8007010B = ERROR_DIRECTORY）**
  —— 命令行带引号被任务计划拼坏了；
- 重建成 XML 后 Next Run Time 停在 8:40 不动，Last Run 不刷新。
与其继续和任务计划的引号/触发器搏斗，改成：**常驻进程自己 sleep 循环**（进程内状态，不依赖引号），
任务计划只留一条 `ONLOGON` 负责开机把它拉起来（不负责每 N 分钟）。

一拍做：`sched_tick`（把到期调度跑掉）→ **12 根分类心跳 + 大脑定级**（2026-10-30 接入）
→ 写心跳 `state/monitor-loop.json` → sleep。
心跳红了（verdict=red）这一拍返回非零，常驻循环照样继续跑，不因一次红就死。
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
# 每多少拍做一次全身扫描（full 档）。10 拍 × 300s ≈ 50 分钟一次。
# 为什么必须有：light 档跳过 body_map，七感官六动作等于不体检 —— 那 12/12 绿是"没测"的绿。
DEEP_EVERY = 10


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


def _tick(deep: bool = False) -> int:
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

    # ── 第二件事：12 根分类心跳（主人令 2026-10-30）────────────────────
    # 为什么接在这里而不是另开一个常驻进程：**已经有一个每分钟级别在跑的循环**，
    # 再起一个就是两份心跳、两处口径。这一拍顺手打一次心跳，代价实测 light 档约 0.3 秒。
    # 心跳红了要不要动手，交给 brain_exec.advise 定级 —— 循环只负责**报**，不越界处置。
    #
    # 🔴 2026-10-30 打磨三（分频深检）：原来这里**永远 light**，而「身」的器官探针
    #    （body_map：七感官六动作逐根回读）是 full 档的 ⇒ **全身扫描从来没在自动链路里跑过**，
    #    报告却 12/12 绿（probe.ok=None 不参与判定）。"看着绿其实没测"就是这么来的。
    #    现在：每拍 light，每 DEEP_EVERY 拍跑一次 full。light 约 0.3s，full 约 6.5s，
    #    默认 10 拍一次 ⇒ 平均每拍多 0.62s，换"七感官一天至少体检一次"。
    hb_summary, hb_err, hb_red = None, None, False
    try:
        from gbt_allinone import brain_exec as _be

        _hb = _be.heartbeat(mode="full" if deep else "light")
        # 🔴 2026-10-30 打磨五：这里原来只 `advise()` —— **常驻循环从来不调 act()**，
        #    于是"可自动的指令"永远停在清单上：深检过期不补、垃圾不清。
        #    act() 内部自带 advise（不重复扫），且只执行 _AUTO_ACTIONS 表内的安全动作
        #    （出错只伤自己抽屉），所以放在常驻循环里是安全的。
        #    实测代价：无动作时只多一次 advise（几毫秒）；有动作时才多一次扫描。
        _act = _be.act(_hb)
        _after = _act.get("after") or {}
        _before = _act.get("before") or {}
        hb_summary = {
            "tentacles_ok": _hb.get("tentacles_ok"),
            "tentacles_total": _hb.get("tentacles_total"),
            "score": _hb.get("score"),
            "verdict": _after.get("verdict"),
            "verdict_before": _before.get("verdict"),
            "counts": _after.get("counts"),
            "headline": _after.get("headline"),
            "signals_by_level": _hb.get("signals_by_level"),
            "ms": _hb.get("elapsed_ms"),
            "deep": deep,
            # 这一拍**真执行了**什么（不是"建议"）。空列表 = 没有可自动的事。
            "acted": [x.get("op") for x in (_act.get("executed") or [])],
            "act_ok": _act.get("ok"),
            "act_skipped": len(_act.get("skipped") or []),
        }
        hb_red = _after.get("verdict") == "red" or _act.get("ok") is False
    except Exception as e:                      # noqa: BLE001
        hb_err = "%s: %s" % (type(e).__name__, str(e)[:120])

    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "ts": round(t0, 3),
           "duration_ms": round((time.time() - t0) * 1000, 1), "pid": os.getpid(),
           "mode": "resident",
           "ran": [{"schedule": r.get("schedule"), "workflow": r.get("workflow"),
                    "status": r.get("status")} for r in ran],
           "count": len(ran), "error": err,
           "heartbeat": hb_summary, "heartbeat_error": hb_err}

    HEART.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    bad = [r for r in ran if str(r.get("status")) != "ok"]
    _tags = []
    if err or bad:
        _tags.append("🔴 " + (err or "调度失败 %s" % bad))
    if hb_err:
        _tags.append("🔴 心跳炸了 " + hb_err)
    elif hb_red:
        _tags.append("🔴 心跳红 " + str((hb_summary or {}).get("headline")))
    elif hb_summary:
        _tags.append("心跳 %s/%s 分%s"
                     % (hb_summary.get("tentacles_ok"),
                        hb_summary.get("tentacles_total"), hb_summary.get("score")))
        # 这一拍真做了什么，必须说出来 —— 不然"自动补齐"只是纸面上的
        _acted = hb_summary.get("acted") or []
        if _acted:
            _tags.append("已自动执行 " + ",".join(str(x) for x in _acted))
    print("[monitor-loop] %s · ran=%d · 心跳%s · %.0f ms · %s"
          % (rec["at"], rec["count"],
             ("%s/%s" % (hb_summary.get("tentacles_ok"), hb_summary.get("tentacles_total")))
             if hb_summary else "n/a",
             rec["duration_ms"],
             " · ".join(_tags) if _tags else "ok"),
          flush=True)
    return 1 if (err or bad or hb_red or hb_err) else 0


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    once = "--once" in args
    interval = INTERVAL
    deep_every = DEEP_EVERY
    if "--interval" in args:
        i = args.index("--interval")
        if i + 1 < len(args):
            try:
                interval = max(30, int(args[i + 1]))
            except ValueError:
                pass
    if "--deep-every" in args:
        i = args.index("--deep-every")
        if i + 1 < len(args):
            try:
                deep_every = max(1, int(args[i + 1]))
            except ValueError:
                pass
    if not _claim_lock():
        print("[monitor-loop] 已有实例在跑（见 %s）—— 本进程退出" % LOCK.name)
        return 0
    if once:
        return _tick(deep=("--deep" in args))
    print("[monitor-loop] 常驻启动 pid=%d · 每 %d 秒一拍 · 每 %d 拍深检一次（Ctrl+C 停）"
          % (os.getpid(), interval, deep_every), flush=True)
    n = 0
    while True:
        # 第 1 拍就深检（先拿一个全身基线），之后每 deep_every 拍一次
        deep = (n % deep_every == 0)
        try:
            _tick(deep=deep)
        except Exception as e:                      # noqa: BLE001
            print("[monitor-loop] 这一拍炸了：%s: %s" % (type(e).__name__, e), flush=True)
        n += 1
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
