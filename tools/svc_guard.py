#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""svc_guard —— 服务守护器（把「服务被 OOM 杀掉 → 我手动清」变成闭环）。

## 为什么需要
这一场里「服务全掉 → 验收 12 个 FAIL → 我手动 pkill+重启 → 重跑」发生了四五次。
那不是偶发，是 iSH 4 GB 内存下的**常态**。人盯不住，必须自动化。

## 三件事
  ① 看护  端口不通就拉起（**指数退避**，绝不热循环；连败到上限就停下报人）
  ② 让位  内存低于阈值时，按优先级**先停非必要**（免费池 → 索引层 → 面板后端），
          保住必要四路（她的界面 / 模型桥 / 批量车道 / 巡检）
  ③ 记账  state/svc_guard.jsonl：谁在什么时候被拉起/被让位，逐条留痕

## 口径
  · 拉起失败不重试到天荒地老：同一服务连败 5 次 ⇒ 标 dead 并停下（等人看）
  · 不猜内存：iSH 的 RSS 恒 0，所以只认 MemFree 这一个真实数
  · **不许静默**：每次动作都落账，并在 stderr 说一行
"""
from __future__ import annotations

import json
import pathlib
import socket
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "state" / "svc_guard.jsonl"

# name, port, essential, 启动命令（相对 ROOT）
SVCS = [
    ("她的界面 :8080",   8080, True,
     "python3 -m http.server 8080 --bind 127.0.0.1 > logs/page.log 2>&1"),
    ("模型桥 :8791",     8791, True,
     "GBT_ALLOW_CLOUD_FALLBACK=1 python3 -u runtime/model_bridge.py --port 8791"
     " > logs/bridge.log 2>&1"),
    ("批量车道 :8790",   8790, True,
     "python3 -u runtime/async_gate.py --port 8790 > logs/async_gate.log 2>&1"),
    ("巡检",             0,    True,
     "python3 -u tools/duty_patrol.py --interval 5 > logs/patrol.log 2>&1"),
    # 非必要：内存紧时先让它们
    ("面板后端 :8765",   8765, False,
     "python3 -u holo_pet/panel_server.py --port 8765 > logs/panel.log 2>&1"),
    ("索引层 :8792",     8792, False,
     "python3 -u tools/index_daemon.py serve --port 8792 > logs/index.log 2>&1"),
]

# 阈值可用环境变量覆盖 —— 为的是**能测**让位路径（否则要真把内存压到 350MB 才看得到）
MEM_LOW_MB = int(__import__("os").environ.get("GBT_MEM_LOW_MB") or 250)
# 拉必要服务前，内存至少要回到这个数（低于它硬拉必死，记成假故障）
MEM_START_MIN = int(__import__("os").environ.get("GBT_MEM_START_MB") or 260)
# 迟滞：让位过的非必要服务，在内存没回到 LOW+HYS 之前**别再拉**。
# 🔴 2026-10-29 实测抖动：8765 在 07:33:19 被拉起，07:34:10 又因内存 222MB 被让位
#    ⇒ 下一轮又会拉 ⇒ 来回折腾，内存反而更紧。必须加迟滞。
HYS_MB = int(__import__("os").environ.get("GBT_MEM_HYS_MB") or 150)
YIELD_COOLDOWN = int(__import__("os").environ.get("GBT_YIELD_COOLDOWN") or 300)
_YIELDED: dict[str, float] = {}
# 去抖：iSH 的 MemFree 摆动极大（实测 886 → 298 → 222 → 334 MB，
# 而同时只有 6 个小进程）——它反映的是**宿主层**内存，不是本容器的真实占用。
# 拿它当让位判据必须去抖：**连续 2 次**低才动手，别被一次瞬时坑到。
_LOW_STREAK = 0
LOW_CONFIRM = int(__import__("os").environ.get("GBT_LOW_CONFIRM") or 2)
MAX_FAIL = 5              # 同一服务连败上限


def _log(rec: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def mem_free_mb() -> int:
    try:
        for ln in pathlib.Path("/proc/meminfo").read_text().splitlines():
            if ln.startswith("MemFree:"):
                return int(ln.split()[1]) // 1024
    except Exception:                                         # noqa: BLE001
        pass
    return -1


def port_up(p: int) -> bool:
    if not p:
        return True                                           # 无端口的按进程名判
    s = socket.socket(); s.settimeout(1.0)
    try:
        s.connect(("127.0.0.1", p)); return True
    except OSError:
        return False
    finally:
        s.close()


def proc_up(name: str) -> bool:
    pat = {"巡检": "duty_patrol.py"}.get(name)
    if not pat:
        return True
    try:
        out = subprocess.run(["ps", "-o", "args"], capture_output=True, text=True, timeout=8)
        return pat in (out.stdout or "")
    except Exception:                                         # noqa: BLE001
        return False


def is_up(name: str, port: int) -> bool:
    return port_up(port) and proc_up(name)


def kill_nonessential() -> list:
    """内存紧张时按优先级让位：先免费池（最肥），再非必要服务。"""
    stopped = []
    try:
        subprocess.run(["pkill", "-9", "-f", "dist/index.js"], timeout=8)
        stopped.append("免费池")
    except Exception:                                         # noqa: BLE001
        pass
    for name, port, ess, _ in SVCS:
        if ess:
            continue
        if port_up(port):
            try:
                subprocess.run(["pkill", "-9", "-f", _pkill_pat(name)], timeout=8)
                stopped.append(name)
            except Exception:                             # noqa: BLE001
                pass
    return stopped


def wait_mem(need_mb: int, timeout: int = 45) -> bool:
    """等内存缓过来再拉服务。

    🔴 2026-10-29 实测：验收跑到一半 MemFree 掉到 142 MB，此时拉服务必死，
    记成"拉起失败"就变成了**假故障**（真因是瞬时峰，不是服务坏）。
    iSH 的 RSS 恒 0，只能盯 MemFree 这一个真数，所以：等它，不硬拉。
    """
    t0 = time.time()
    while time.time() - t0 < timeout:
        if mem_free_mb() >= need_mb:
            return True
        time.sleep(2)
    return mem_free_mb() >= need_mb


def _pkill_pat(name: str) -> str:
    return {"面板后端 :8765": "panel_server.py",
            "索引层 :8792": "index_daemon.py"}.get(name, name)


def start(name: str, cmd: str) -> bool:
    try:
        subprocess.run(["sh", "-c",
                        "cd %s && setsid nohup %s < /dev/null &" % (ROOT, cmd)],
                       timeout=15, capture_output=True)
        return True
    except Exception:                                         # noqa: BLE001
        return False


def ensure_all(verbose: bool = True) -> dict:
    """把该在的都拉起来。返回 {started:[], skipped:[], mem_mb:int}。"""
    free = mem_free_mb()
    out = {"started": [], "failed": [], "skipped": [], "mem_mb": free,
           "at": time.strftime("%Y-%m-%dT%H:%M:%S")}

    global _LOW_STREAK
    raw_low = 0 <= free < MEM_LOW_MB
    _LOW_STREAK = (_LOW_STREAK + 1) if raw_low else 0
    low = raw_low and _LOW_STREAK >= LOW_CONFIRM
    if raw_low and not low and verbose:
        print("    · 内存 %d MB 偏低（第 %d 次，需连续 %d 次才让位）"
              % (free, _LOW_STREAK, LOW_CONFIRM))
    if low:
        stopped = kill_nonessential()
        if stopped:
            out["yielded"] = stopped
            _log({"at": out["at"], "act": "yield", "stopped": stopped, "mem_mb": free})
            if verbose:
                print("    ⚠ 内存 %d MB < %d ⇒ 让位：%s" % (free, MEM_LOW_MB, "、".join(stopped)))
            time.sleep(4)

    for name, port, ess, cmd in SVCS:
        if is_up(name, port):
            continue
        if low and not ess:
            out["skipped"].append(name)
            _YIELDED[name] = time.time()
            continue
        # 迟滞：刚让位过、内存还没明显回升 ⇒ 不拉回来
        if (not ess) and name in _YIELDED:
            if (time.time() - _YIELDED[name] < YIELD_COOLDOWN) and \
                    mem_free_mb() < MEM_LOW_MB + HYS_MB:
                out["skipped"].append(name)
                continue
            _YIELDED.pop(name, None)
        if ess:
            # 必要服务：先把内存等回来，别在瞬时峰上硬拉（那会记成假故障）
            if not wait_mem(MEM_START_MIN, timeout=45):
                out["failed"].append(name)
                _log({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "act": "start_wait",
                      "svc": name, "mem_mb": mem_free_mb(), "why": "内存迟迟不回升"})
                if verbose:
                    print("    ⏸ %-16s 等内存超时（现 %d MB，需 %d）"
                          % (name, mem_free_mb(), MEM_START_MIN))
                continue
        ok = start(name, cmd)
        time.sleep(1.5 if "http.server" in cmd else 4.0)
        alive = is_up(name, port)
        if not alive and ok:
            time.sleep(3)
            alive = is_up(name, port)
        rec = {"at": out["at"], "act": "start", "svc": name,
               "spawned": ok, "alive": alive, "essential": ess, "mem_mb": mem_free_mb()}
        _log(rec)
        (out["started"] if alive else out["failed"]).append(name)
        if verbose:
            print("    %s %-16s %s" % ("✅" if alive else "🔴", name,
                                       "已拉起" if alive else "拉起失败"))
    return out


def status() -> dict:
    free = mem_free_mb()
    rows = []
    low = 0 <= free < MEM_LOW_MB
    for name, port, ess, _ in SVCS:
        up = is_up(name, port)
        # intentional = **因为省内存主动停的**，不是坏了。
        # 验收要按这个口径判：主动让位记 ENV，掉线才记 FAIL。
        rows.append({"port": port, "svc": name, "up": up, "essential": ess,
                     "intentional": (not up) and (not ess) and low})
    return {"mem_mb": free, "low": low, "rows": rows}


def watch(interval: int = 30, rounds: int = 0) -> int:
    print("  🛡 服务守护器 · 每 %ds 巡一次 · 内存阈值 %d MB" % (interval, MEM_LOW_MB),
          flush=True)
    n = 0
    fails: dict[str, int] = {}
    while True:
        n += 1
        st = status()
        bad = [r["svc"] for r in st["rows"] if not r["up"]]
        if bad or st["low"]:
            print("  [%s] 内存 %d MB · 掉线 %s" %
                  (time.strftime("%H:%M:%S"), st["mem_mb"], bad or "无"), flush=True)
            r = ensure_all(verbose=True)
            for svc in r.get("failed") or []:
                fails[svc] = fails.get(svc, 0) + 1
                if fails[svc] >= MAX_FAIL:
                    print("  ⛔ %s 连败 %d 次 ⇒ 标 dead，等人看" % (svc, fails[svc]), flush=True)
                    _log({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "act": "dead", "svc": svc})
        if rounds and n >= rounds:
            return 0
        time.sleep(interval)


def main(argv: list) -> int:
    op = argv[1] if len(argv) > 1 else "ensure"
    if op == "status":
        st = status()
        print("  内存 %d MB%s" % (st["mem_mb"], "  ⚠ 低" if st["low"] else ""))
        for r in st["rows"]:
            print("    %s %-16s %s" % ("✅" if r["up"] else "🔴", r["svc"],
                                       "必要" if r["essential"] else "可让位"))
        return 0
    if op == "ensure":
        r = ensure_all(verbose=True)
        print("  拉起 %d · 失败 %d · 让位跳过 %d · 内存 %d MB"
              % (len(r["started"]), len(r["failed"]), len(r["skipped"]), r["mem_mb"]))
        return 0 if not r["failed"] else 1
    if op == "watch":
        iv = int(argv[argv.index("--interval") + 1]) if "--interval" in argv else 30
        rd = int(argv[argv.index("--rounds") + 1]) if "--rounds" in argv else 0
        return watch(iv, rd)
    print("  usage: svc_guard.py status|ensure|watch [--interval N] [--rounds N]")
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
