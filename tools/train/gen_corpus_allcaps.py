# -*- coding: utf-8 -*-
"""gen_corpus_allcaps -- 全方位覆盖：把名册里每一位能力位都变成训练语料（现读生成）。"""
from __future__ import annotations
import json, re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ATLAS = ROOT / "state" / "skill_atlas.json"
OUT = ROOT / ".scratch" / "allcaps.jsonl"
STAT = ROOT / "state" / "train" / "allcaps_coverage.json"
TICK = chr(96)


def load_caps():
    j = json.loads(ATLAS.read_text(encoding="utf-8"))
    caps = j.get("caps") or j.get("capabilities") or []
    out = []
    for c in caps:
        if not isinstance(c, dict):
            continue
        name = c.get("kind") or c.get("name") or ""
        if not name:
            continue
        out.append({"name": str(name), "domain": str(c.get("domain") or "未标注"),
                    "desc": str(c.get("desc") or c.get("description") or "")})
    return out


def ops_of(name):
    p = ROOT / "gbt_allinone" / (name + ".py")
    if not p.is_file():
        return "未读到"
    t = p.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"OPS\s*=\s*\(([^)]*)\)", t)
    if not m:
        return "未读到"
    parts = [x.strip().strip(chr(34)).strip(chr(39)) for x in m.group(1).split(",")]
    return " / ".join(x for x in parts if x)


def clean(s, n=200):
    s = (s or "").replace("*", "").replace(TICK, "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()[:n]


def main():
    caps = load_caps()
    rows, doms, seen = [], Counter(), set()
    for c in caps:
        name = c["name"]
        if name in seen:
            continue
        seen.add(name)
        dom = c["domain"] or "未标注"
        desc = clean(c["desc"])
        ops = ops_of(name)
        doms[dom] += 1
        fam = "能力位-" + dom
        rows.append({"instruction": "怎么调能力位 " + name + " ？", "input": "", "family": fam,
                     "output": "走唯一门 five-dim.py cap " + name + "（载荷给 op 与参数）。域=" + dom +
                               ("；op=" + ops if ops != "未读到" else "；op 未读到（以模块 run() 为准）")})
        rows.append({"instruction": name + " 是什么，能干什么？", "input": "", "family": fam,
                     "output": (desc or "未读到描述") + "（域=" + dom + "）"})
        rows.append({"instruction": name + " 属于哪个域，要不要授权？", "input": "", "family": fam,
                     "output": "域=" + dom + "。要不要授权不靠猜：由作用域门现读 + 主人在终端发钥匙；无钥匙即如实报缺哪个作用域。"})
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + chr(10) for r in rows), encoding="utf-8")
    blob = OUT.read_bytes()
    STAT.write_text(json.dumps({"gen": "allcaps", "caps": len(seen), "rows": len(rows), "bytes": len(blob),
                                "by_domain": dict(doms.most_common())}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("全位覆盖语料：位 %d · 条 %d · 字节 %d -> %s" % (len(seen), len(rows), len(blob), OUT.name))
    print("按域（前 12）：" + ", ".join("%s=%d" % (k, v) for k, v in doms.most_common(12)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
