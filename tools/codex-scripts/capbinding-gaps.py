# -*- coding: utf-8 -*-
"""gap-scan-capbindings -- 逐条列出能力位 desc 里的「未接线/未读到/缺」，并给处置分类。"""
from __future__ import annotations
import json, time
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "state" / "cap-bindings.json"
OUT = ROOT / "state" / "capbinding-gaps.json"
MARKS = ("未接线", "未读到", "缺授权", "缺票", "未装", "不在 PATH", "待接线", "未取证", "未验")

def walk(node, name=None, out=None):
    if out is None:
        out = []
    if isinstance(node, dict):
        nm = node.get("cap") or node.get("name") or node.get("id") or name
        d = node.get("desc")
        if isinstance(d, str) and any(m in d for m in MARKS):
            out.append({"cap": nm, "desc": d[:220]})
        for k, v in node.items():
            walk(v, k, out)
    elif isinstance(node, list):
        for v in node:
            walk(v, name, out)
    return out

def classify(d):
    if "privacy_read" in d or "需人工授权" in d or "缺票" in d:
        return "缺票(主人发钥匙)"
    if "未装" in d or "不在 PATH" in d or "缺依赖" in d:
        return "缺依赖(可补件)"
    if "未接线" in d or "待接线" in d:
        return "未接线(可接)"
    if "未读到" in d or "未取证" in d:
        return "未取证(需通道/出处)"
    return "其他"

def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    items = walk(data)
    seen, uniq = set(), []
    for it in items:
        k = (it["cap"], it["desc"][:60])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(it)
    for it in uniq:
        it["class"] = classify(it["desc"])
    from collections import Counter
    by = Counter(x["class"] for x in uniq)
    OUT.write_text(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "total": len(uniq),
                               "by_class": dict(by), "items": uniq}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("cap-bindings 缺口：**%d 条**（落 %s）" % (len(uniq), OUT.relative_to(ROOT)))
    for k, v in by.most_common():
        print("   %-20s %d" % (k, v))
    for it in uniq[:12]:
        print("   [%s] %s -> %s" % (it["class"], str(it["cap"])[:22], it["desc"][:96]))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
