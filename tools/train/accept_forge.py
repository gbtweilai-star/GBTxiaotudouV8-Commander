# -*- coding: utf-8 -*-
"""accept_forge -- 技能蒸馏五式验收（判据按题分派）"""
from __future__ import annotations
import argparse, json
from pathlib import Path
CASES = {
    "核心是什么": [("不是复制人", "思维框架"), ("心智模型",)],
    "两种入口": [("明确", "模糊", "诊断")],
    "全网情报": [("投票", "金额", "计分"), ("交叉印证", "平台")],
    "分工": [("book_skill",), ("经验",)],
    "说话方式": [("隐私", "脱敏"), ("模拟", "不冒充")],
    "反蒸馏": [("交出版", "消毒"), ("私有备份", "核心")],
    "怎么调": [("skill_forge",), ("cap", "five-dim")],
    "合成一个能力位": [("分叉", "一个能力位", "skill_forge")],
}


def main():
    ap = argparse.ArgumentParser(description="技能蒸馏五式验收")
    ap.add_argument("--answers", required=True)
    a = ap.parse_args()
    rows = [json.loads(l) for l in Path(a.answers).read_text(encoding="utf-8").splitlines() if l.strip()]
    ok = 0
    for i, r in enumerate(rows, 1):
        q = r.get("q") or ""
        ans = r.get("a") or ""
        rule = None
        for key, rr in CASES.items():
            if key in q:
                rule = rr
                break
        if rule is None:
            print("  %-3d RED  无对应判据（题=%s）" % (i, q[:18]))
            continue
        miss = [list(g) for g in rule if not any(w.lower() in ans.lower() for w in g)]
        good = not miss
        print("  %-3d %s 缺 %s" % (i, "OK " if good else "RED", miss or "-"))
        ok += 1 if good else 0
    print("== 技能蒸馏五式：%d/%d ==" % (ok, len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
