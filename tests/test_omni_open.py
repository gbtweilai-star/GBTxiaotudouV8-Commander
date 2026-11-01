# -*- coding: utf-8 -*-
"""万能插·自动识别插口 + 自动配备插上 的判据（`omni_open`）。

主人令 2026-11-01（修正）：「万能插有自动识别插口，自动配备插上，而不是固定的六插口」

钉四件事：
  ① **种类由发现决定**：不许出现写死的六类清单（读快照里的 `kinds`，它来自 discover）；
  ② **每根插头都有出处**：surface（从哪个面发现的）+ target + ok/原因；
  ③ **ensure() 不阻塞**：快照过期只在后台重扫，调用侧秒回；
  ④ **钩子在分派前**：随便调一个能力，快照必须被读到/触发（证明"自动"不是靠人记得）。

跑法：python tests/test_omni_open.py
"""
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FAILED = []


def check(name, cond, detail=""):
    print(("  ok   " if cond else "  FAIL ") + name + ("" if cond else "  " + str(detail)))
    if not cond:
        FAILED.append(name)


def main() -> int:
    from gbt_allinone.caps_registry import BENIGN_CAPS
    from gbt_allinone.tentacle import omni_open as OO

    print("[1] 五处齐")
    check("omni_open 在注册表", "omni_open" in BENIGN_CAPS)
    api = open(os.path.join(ROOT, "gbt_allinone", "api.py"), encoding="utf-8").read()
    check("api.py 有分派分支", 'if kind == "omni_open"' in api)
    check("钩子在分派前", api.find("_OO.ensure()") != -1
          and api.find("_OO.ensure()") < api.find("result = _run_benign"))

    print("[2] 种类由发现决定（不是固定六插口）")
    snap = OO._load()
    if not snap:
        print("  ..  没有快照，先扫一轮（≈26s）")
        snap = OO.scan()
    kids = snap.get("kinds") or {}
    check("快照里有 kinds", isinstance(kids, dict) and bool(kids), kids)
    check("kinds 的键来自可插面（port/ai/file/process/app/serial）",
          set(kids).issubset({"port", "ai", "file", "process", "app", "serial", "unknown"}), list(kids))
    check("插头数 = 各类之和", sum(kids.values()) == snap.get("插头数"),
          (kids, snap.get("插头数")))
    check("每根插头都有 surface+target",
          all(p.get("surface") and p.get("target") for p in (snap.get("plugs") or [])[:50]))
    check("没连上的必须有原因",
          all(p.get("reason") for p in (snap.get("plugs") or []) if p.get("ok") is False))

    print("[3] ensure() 不阻塞（只读快照 + 后台补扫）")
    t0 = time.time()
    e = OO.ensure()
    dt = time.time() - t0
    check("ensure 秒回（<1.5s）", dt < 1.5, "%.2fs" % dt)
    check("ensure 说明是否在扫", "scanning" in e, list(e))

    print("[4] 钩子真的跑了（清空快照 → 调能力 → 必须被补上）")
    if OO.SNAPSHOT.exists():
        OO.SNAPSHOT.rename(OO.SNAPSHOT.with_suffix(".bak"))
    import gbt_allinone as g
    g.run_task("echo", {"x": 1}, probe=True)
    triggered = e.get("scanning") or OO._SCAN_STATE.get("running") or OO._load() != {}
    check("调一个能力 ⇒ 触发/已有插座快照", bool(triggered), "钩子没跑")
    bak = OO.SNAPSHOT.with_suffix(".bak")
    if bak.exists() and not OO.SNAPSHOT.exists():
        bak.rename(OO.SNAPSHOT)

    print()
    if FAILED:
        print("FAILED %d: %s" % (len(FAILED), ", ".join(FAILED)))
        return 1
    print("ALL OK —— 插口是扫出来的，插头是自动配上的，不是写死的六类")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
