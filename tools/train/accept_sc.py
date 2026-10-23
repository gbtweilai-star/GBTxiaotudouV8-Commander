# -*- coding: utf-8 -*-
"""accept_sc -- 作品解剖展示验收"""
from __future__ import annotations
import argparse, json
from pathlib import Path
CASES = {
    "怎么把一个概念": [("会动", "实物"), ("比喻", "例", "请慢读")],
    "作品由什么构成": [("零件",)],
    "展示框": [("标题",), ("读数",), ("署名",)],
    "运动": [("平静", "克制")],
    "读数同源": [("同一个模型", "同源", "驱动")],
    "自检": [("关节",)],
    "护栏": [("署名",), ("未验",), ("读数",)],
    "命令怎么调": [("showcase_ops",), ("cap", "five-dim")],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", required=True)
    a = ap.parse_args()
    rows = [json.loads(l) for l in Path(a.answers).read_text(encoding="utf-8").splitlines() if l.strip()]
    ok = 0
    for i, r in enumerate(rows, 1):
        q = r.get("q") or ""
        ans = r.get("a") or ""
        rule = next((rr for k, rr in CASES.items() if k in q), None)
        if rule is None:
            print("  %-3d RED  无对应判据" % i)
            continue
        miss = [list(g) for g in rule if not any(w.lower() in ans.lower() for w in g)]
        good = not miss
        print("  %-3d %s 缺 %s" % (i, "OK " if good else "RED", miss or "-"))
        ok += 1 if good else 0
    print("== 作品解剖展示：%d/%d ==" % (ok, len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
