# -*- coding: utf-8 -*-
"""直接调用「上帝视角」——把 W3 设计的四视图数据源逐个真调，看哪几格是空的。

依据《W3上帝视角镜像方案.md》§十 +《holo_pet多窗口架构设计.md》§3.4：
  四视图 = 看自己 / 看任务 / 看环境 / 看账本
  B1.6：任务队列 / 服务表 / 账本 / 配额 —— 窗口**直读** store（不经 /api/state）

本脚本只读，不写盘、不起窗口。结论以「盘上真有没有」为准，不按文档口径推断。
"""
import json
import os
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def size(p):
    try:
        return os.path.getsize(p)
    except Exception:
        return None


def show(label, path, note=""):
    s = size(ROOT / path)
    flag = "有" if s is not None else "**无**"
    extra = ("%d B" % s) if s is not None else ""
    print("  %-34s %-6s %-12s %s" % (path, flag, extra, note))
    return s is not None


print("=" * 96)
print("① 上帝视角窗口本体（W3 产物）")
print("=" * 96)
for p in ("holo_pet_w3/index.html", "holo_pet_w3/window.css",
          "holo_pet_w3/shell/windows.json", "holo_pet_w3/shell/main.cjs",
          "holo_pet_w3/ledger/ledger_store.py"):
    show("", p)

print("\n  窗口注册表 windows.json 内容：")
try:
    wj = json.loads((ROOT / "holo_pet_w3/shell/windows.json").read_text(encoding="utf-8-sig"))
    ids = [w.get("id") for w in (wj.get("windows") or [])]
    print("     登记窗口: %s" % ids)
    print("     registry_note: %s" % str(wj.get("registry_note"))[:110])
except Exception as e:  # noqa: BLE001
    print("     读不到: %s" % e)

print("\n" + "=" * 96)
print("② 四视图数据源（窗口直读 store）")
print("=" * 96)
views = {
    "看自己（cpu/内存/磁盘）": [("holo_pet/mind_engine.py", "psutil 读数"),
                       ("holo_pet_w3/selfvision", "自我视觉验证（设计说 P1/P2）")],
    "看任务（队列/管线）": [("gbt_allinone/store/tasks.json", "任务队列"),
                   ("gbt_allinone/store/pipeline", "管线目录")],
    "看环境（服务探活）": [("holo_pet/services.py", "探活实现")],
    "看账本（四路账本）": [("gbt_allinone/store/ledger", "**常驻账本**（设计要求的落点）"),
                  ("gbt_allinone/store/health", "健康账本")],
}
for name, items in views.items():
    print("\n  ● %s" % name)
    for p, note in items:
        show("", p, note)

print("\n" + "=" * 96)
print("③ 账本常驻化：设计落点 store/ledger/ vs 探针产物 .scratch/")
print("=" * 96)
led = ROOT / "gbt_allinone/store/ledger"
if led.exists():
    fs = sorted(led.iterdir())
    print("  store/ledger/ 存在，%d 项: %s" % (len(fs), [f.name for f in fs][:10]))
else:
    print("  **store/ledger/ 不在** —— 设计里「账本常驻化」这一格没落地")
probe = sorted((ROOT / ".scratch").glob("codex_v2_*_ledger.jsonl"))
print("  .scratch 里的探针账本产物: %d 个" % len(probe))
for p in probe[:8]:
    print("     %-52s %d B" % (p.name, p.stat().st_size))

print("\n" + "=" * 96)
print("④ 上帝视角能不能被「调用」（能力位 / 路由）")
print("=" * 96)
from gbt_allinone import api  # noqa: E402
names = [r["name"] for r in api.list_capabilities()]
cand = [n for n in names if any(k in n.lower() for k in ("god", "view", "monitor", "hud", "holo"))]
print("  能力位里与上帝视角/监控相关的: %s" % (cand or "**一个都没有**"))
print("  结论：上帝视角目前**只能作为 Electron 窗口看**，没有 run_task 可调用的能力位/路由。")
