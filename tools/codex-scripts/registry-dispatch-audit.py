#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""注册表 ↔ 分派面 对账（F12 的尺子）——**只读**。

F12 的原话是「能力注册表没有收录一整套真在生产上跑、真过门、真能成功的操作
（room_*/collab_*/peer_register/notion/tripo/mirror_space/qiankun/deployment_rehearsal 等）」。
但"名字不对"和"没收录"是两件事：
  · 有的名字是**模块名**（`qiankun` / `mirror_space` / `deployment_rehearsal`），它们被
    `one_key_deploy` / `mirror_scan` / `mirror_plan`… 这些 **kind** 分派到 —— 不是缺能力位；
  · 有的名字**真的能被当 kind 分派**却不在注册表里 —— 那才是真缺口。
本件把两种分开量，缺口的才叫 F12 成立。

用法：py -3.14 tools/codex-scripts/registry-dispatch-audit.py [--json]
"""
import argparse
import ast
import json
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
API = os.path.join(ROOT, "gbt_allinone", "api.py")

# F12 点名的那些名字
WATCH = ["room_create", "room_plan", "room_simulate", "room_parity", "room_rehearse",
         "room_release", "collab_gateway", "peer_register", "notion_bridge", "tripo",
         "mirror_space", "qiankun", "deployment_rehearsal", "one_key_deploy"]


def registry_names():
    sys.path.insert(0, ROOT)
    from gbt_allinone import caps_registry as cr
    return set(cr.BENIGN_CAPS.keys())


def dispatched_kinds():
    src = open(API, encoding="utf-8").read()
    return set(re.findall(r'if\s+kind\s*==\s*"([A-Za-z0-9_]+)"', src))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    reg = registry_names()
    kinds = dispatched_kinds()
    rows = []
    for n in WATCH:
        rows.append({
            "name": n,
            "in_registry": n in reg,
            "dispatchable_as_kind": n in kinds,
            "判定": ("注册表有" if n in reg else
                     "模块名（由别的 kind 分派）" if n not in kinds else
                     "**真缺口：能当 kind 分派但注册表没有**"),
        })
    gap = [r for r in rows if not r["in_registry"] and r["dispatchable_as_kind"]]
    orphan = [k for k in sorted(kinds) if k not in reg]
    if a.json:
        print(json.dumps({"registry": len(reg), "kinds": len(kinds),
                          "watch": rows, "gap": [r["name"] for r in gap],
                          "kinds_not_in_registry": orphan}, ensure_ascii=False, indent=2))
        return 0 if not gap else 1
    print("注册表 %d 条 ｜ api.py 的 kind 分支 %d 个" % (len(reg), len(kinds)))
    print("-" * 86)
    for r in rows:
        print("  %-24s 注册表=%-5s 可当kind=%-5s %s"
              % (r["name"], r["in_registry"], r["dispatchable_as_kind"], r["判定"]))
    print("-" * 86)
    print("F12 点名的名字里，**真缺口**（可当 kind 分派却不在注册表）：%s"
          % (", ".join(r["name"] for r in gap) or "无"))
    print("全部 kind 里不在注册表的：%d 个%s" % (len(orphan), ("：" + ", ".join(orphan[:15])) if orphan else ""))
    print("-" * 86)
    print("口径：模块名 ≠ 能力位名。模块名由别的 kind 分派是正常设计，不是缺收录。")
    return 0 if not gap else 1


if __name__ == "__main__":
    sys.exit(main())
