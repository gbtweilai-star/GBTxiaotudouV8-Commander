#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""量一件事（只读）：**图鉴采集若改递归，会多收多少条**（F24 的决策依据）。

F24 现状：`omni.py collect_skills()` 只扫每个根的**直接子目录**（`root.iterdir()`），
嵌套技能（`<根>/<类>/<名>/SKILL.md`）永远不入册。修法有两条：
  ① 改递归 —— 但图鉴会多出一批，得先知道多多少、都是些什么；
  ② 保持一层、把嵌套件登记成"不进图鉴的例外"。
本件只回答①要的那个数，不改任何东西。

用法：py -3.14 tools/codex-scripts/nested-skill-probe.py [--json]
"""
import json
import os
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = r"C:\Users\ADMIN\Desktop\GBT小土豆V8"
HOME = os.path.expanduser("~")
SKIP = {"__pycache__", ".git", "node_modules", ".venv", "site-packages"}
CONTAINERS = [
    os.path.join(ROOT, "skills"),
    os.path.join(ROOT, "plugins"),
    os.path.join(HOME, ".openclaw-autoclaw", "skills"),
    os.path.join(HOME, ".dsh", ".agent-presets"),
]


def atlas_names():
    p = os.path.join(ROOT, "state", "skill_atlas.json")
    j = json.load(open(p, encoding="utf-8"))
    return {s.get("name") for s in (j.get("skills") or [])}


def front_name(d):
    p = os.path.join(d, "SKILL.md")
    try:
        head = open(p, encoding="utf-8", errors="replace").read(800)
    except OSError:
        return os.path.basename(d)
    m = re.search(r"(?m)^name:\s*(.+)$", head)
    return (m.group(1).strip().strip("\"'") if m else os.path.basename(d))


def main():
    as_json = "--json" in sys.argv
    atlas = atlas_names()
    direct, nested = [], []
    for base in CONTAINERS:
        if not os.path.isdir(base):
            continue
        for dp, dn, fn in os.walk(base):
            dn[:] = [d for d in dn if d not in SKIP]
            if "SKILL.md" not in fn:
                continue
            rel = os.path.relpath(dp, base)
            depth = len(rel.split(os.sep))
            row = {"path": dp, "name": front_name(dp), "depth": depth,
                   "in_atlas": front_name(dp) in atlas, "container": base}
            (direct if depth <= 1 else nested).append(row)

    add = [r for r in nested if not r["in_atlas"]]
    by_container = {}
    for r in add:
        by_container.setdefault(r["container"], []).append(r)

    out = {
        "直接子目录技能": len(direct), "嵌套技能": len(nested),
        "递归后**新增入册**": len(add),
        "新增里已在图鉴的": len([r for r in nested if r["in_atlas"]]),
        "按容器分布": {k: len(v) for k, v in by_container.items()},
        "样本": [{"name": r["name"], "path": r["path"]} for r in add[:15]],
    }
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 0
    print("我方四个容器里：直接子目录技能 %d · **嵌套技能 %d**" % (len(direct), len(nested)))
    print("⇒ 图鉴采集改递归，**会多收 %d 条**（其中 %d 条其实已在册、只是名字不同）"
          % (len(add), len([r for r in nested if r["in_atlas"]])))
    for k, v in by_container.items():
        print("   %-52s %3d 条" % (k, len(v)))
    print("新增样例（前 15）：")
    for r in add[:15]:
        print("   · %-40s %s" % (r["name"], r["path"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
