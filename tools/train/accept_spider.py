# -*- coding: utf-8 -*-
"""accept_spider -- 自适应抓取验收（判据按题分派）"""
from __future__ import annotations
import argparse, json
from pathlib import Path
CASES = {
    "Scrapling 是什么": [("adaptive", "自适应"), ("爬取", "抓取")],
    "抓取最怕什么": [("选择器",), ("自适应", "回找", "指纹")],
    "边界": [("robots", "授权"), ("验证码", "撞库", "隐私")],
    "计划怎么写": [("范围", "字段"), ("断点", "限速", "去重")],
    "抽取口径": [("字段表", "空值"), ("出处", "URL")],
    "算可信": [("URL",), ("时间", "留痕")],
    "命令怎么调": [("spider_ops",), ("cap", "five-dim")],
}


def main():
    ap = argparse.ArgumentParser(description="自适应抓取验收")
    ap.add_argument("--answers", required=True)
    a = ap.parse_args()
    rows = [json.loads(l) for l in Path(a.answers).read_text(encoding="utf-8").splitlines() if l.strip()]
    ok = 0
    for i, r in enumerate(rows, 1):
        q = r.get("q") or ""
        ans = r.get("a") or ""
        rule = next((rr for key, rr in CASES.items() if key in q), None)
        if rule is None:
            print("  %-3d RED  无对应判据（题=%s）" % (i, q[:18]))
            continue
        miss = [list(g) for g in rule if not any(w.lower() in ans.lower() for w in g)]
        good = not miss
        print("  %-3d %s 缺 %s" % (i, "OK " if good else "RED", miss or "-"))
        ok += 1 if good else 0
    print("== 自适应抓取：%d/%d ==" % (ok, len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
