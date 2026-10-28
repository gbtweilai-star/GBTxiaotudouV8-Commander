#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""orphan_audit —— 全量查"能力实现好了但没人接"（孤儿）。

为什么要有它：这一场里我反复犯同一个错 ——
  ring_context 做了不接、context_guard 做了不接、src= 参数只写在回复里没写进代码。
  每次都是主人指出才发现。靠人盯不住，得用尺子量。

三层口径（**不混**）：
  ① 可调      run_task 认得（registry 有 handler / api 有分发）
  ② 活接线    有**活路径**真的在调它（桥/语音/页面/巡检/验收）
  ③ 孤儿      可调，但活路径里查不到调用点

排除的"非活路径"（这些是登记处/文档，不算接线）：
  gbt_allinone/caps_registry.py · data/capabilities.json
  holo_pet_w3/brain/caps/*.html（能力说明页）· docs/**

口径：**孤儿 ≠ 坏**。有的位是给外部调用方用的（run_task 直达），
      这里只是把"我们自己的活路径有没有用它"量出来，不替人决定删留。
"""
from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# ── 活路径：真的会去调能力的入口 ──
LIVE_FILES = [
    "runtime/model_bridge.py",
    "runtime/async_gate.py",
    "runtime/adaptive_context.py",
    "tools/voice_loop.py",
    "tools/tentacle_bus.py",
    "tools/context_guard.py",
    "tools/duty_patrol.py",
    "tools/acceptance.py",
    "tools/brain_attention.py",
    "tools/brain_align.py",
    "tools/mirror_panel.py",
    "tools/plug_a19.py",
    "tools/up.sh",
]
# 🔴 2026-10-28 第一版这里写的是 holo_pet_w3/*/*.js —— **错的**。
#   那个 glob 会把 brain-data.js / capabilities-data.js / energy-data.js 也吞进来，
#   而它们是"把 348 位全列一遍"的**数据文件**，不是调用者。
#   结果审计报 348/348 全接线、0 孤儿 —— 假绿。
#   仪器先得可信，否则量出来的数比不量更糟。
LIVE_GLOBS = [
    # ── 我这几天新接的活路径工具（接了就登记，否则审计看不见）──
    "tools/memory_unify.py",       # 记忆统一层：喂 context_vault / 跨源 recall
    "tools/voice_loop.py",         # 语音环：知识闸 / 输出纪律 / 真实闸 / 上下文守卫
    "tools/dh_preflight.py",       # 数字人上场前的资产闸
    "tools/duty_patrol.py",        # 低频真实巡检
    "tools/context_guard.py",      # 上下文异常 → 主脑 → 大脑 → 纠正
    "tools/tentacle_bus.py",       # 触手总线：嘴/耳/播
    "holo_pet_w3/model-chat/index.html",
    "holo_pet_w3/digital-human/index.html",
    "holo_pet_w3/panel/index.html",
    "holo_pet_w3/projection/index.html",
    "holo_pet_w3/projection/ar.html",
    "holo_pet_w3/projection/camera.html",
    "holo_pet_w3/index.html",
]
# 这些是"登记处 / 说明书"，不是活路径（命中它们不代表有人调用）
EXCLUDE_NAME_HINTS = ("-data.js", "_data.js", "capabilities-data", "energy-data",
                      "brain-data", "/brain/caps/", "/capabilities/")


def caps() -> list[str]:
    try:
        s = subprocess.run(
            [sys.executable, "-c",
             "import sys,json;sys.path.insert(0,%r);"
             "from gbt_allinone.caps_registry import all_caps;"
             "print(json.dumps([c.get(\'name\') for c in all_caps() "
             "if isinstance(c,dict)],ensure_ascii=False))" % str(ROOT)],
            capture_output=True, text=True, timeout=180, cwd=str(ROOT))
        out = json.loads(s.stdout or "[]")
        if out:
            return sorted(set(str(x) for x in out if x))
    except Exception:                                        # noqa: BLE001
        pass
    p = ROOT / "data" / "capabilities.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    rows = d if isinstance(d, list) else (d.get("capabilities") or d.get("items") or [])
    return sorted(set(str(r.get("name")) for r in rows if isinstance(r, dict) and r.get("name")))


def live_text() -> str:
    buf = []
    for rel in LIVE_FILES:
        f = ROOT / rel
        if f.is_file():
            try:
                buf.append(f.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
    for g in LIVE_GLOBS:
        for f in ROOT.glob(g):
            rel = str(f.relative_to(ROOT))
            if any(h in rel for h in EXCLUDE_NAME_HINTS):
                continue
            try:
                buf.append(f.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
    return "\n".join(buf)


def callable_caps() -> set[str]:
    """run_task 能直接叫到的（api.py 里有分发）。"""
    api = ROOT / "gbt_allinone" / "api.py"
    if not api.is_file():
        return set()
    s = api.read_text(encoding="utf-8", errors="ignore")
    names = set()
    for m in re.finditer(r'kind\s*==\s*"([a-z0-9_]+)"', s):
        names.add(m.group(1))
    for m in re.finditer(r'kind\s+in\s*\(([^)]+)\)', s):
        for q in re.findall(r'"([a-z0-9_]+)"', m.group(1)):
            names.add(q)
    return names


def main() -> int:
    names = caps()
    live = live_text()
    callable_set = callable_caps()
    wired, orphan, not_callable = [], [], []
    for n in names:
        hit = re.search(r"(?<![A-Za-z0-9_])" + re.escape(n) + r"(?![A-Za-z0-9_])", live)
        if hit:
            wired.append(n)
        elif n in callable_set:
            orphan.append(n)
        else:
            not_callable.append(n)

    print("  ═══ 全量 %d 位 · 孤儿审计 ═══\n" % len(names))
    print("  ① 活接线（有活路径在调）  %3d  %.0f%%" % (len(wired), len(wired)/max(1,len(names))*100))
    print("  ② 孤儿（可调但没人调）    %3d  %.0f%%" % (len(orphan), len(orphan)/max(1,len(names))*100))
    print("  ③ 未分发（api 里无分支）  %3d  %.0f%%" % (len(not_callable), len(not_callable)/max(1,len(names))*100))
    print()
    if orphan:
        print("  ── 孤儿清单（可调，但活路径查不到）──")
        for i in range(0, len(orphan), 4):
            print("    " + "  ".join("%-20s" % x for x in orphan[i:i+4]))
        print()
    if not_callable:
        print("  ── 未分发（得先确认它怎么被调）──")
        for i in range(0, len(not_callable), 4):
            print("    " + "  ".join("%-20s" % x for x in not_callable[i:i+4]))
        print()
    out = {"total": len(names), "wired": wired, "orphan": orphan,
           "not_dispatched": not_callable}
    (ROOT / "state").mkdir(exist_ok=True)
    (ROOT / "state" / "orphan_audit.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  报告: state/orphan_audit.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
