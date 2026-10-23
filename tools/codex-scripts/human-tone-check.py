# -*- coding: utf-8 -*-
"""human-tone-check -- 「AI 味」机检：禁词表 + 结构味（三连同长句/平衡三项/连接词开头）。
用法：--file <文本> | --text "<文本>"。命中即报，退出码非零=有 AI 味。
"""
from __future__ import annotations
import argparse, re, sys

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


BANNED = ["delve", "landscape", "realm", "tapestry", "testament to", "navigate the complexities", "underscore",
          "pivotal", "embark on a journey", "unlock the potential", "game-changer", "cutting-edge", "seamless",
          "robust", "leverage", "foster", "holistic", "elevate"]
CN_BANNED = ["\u5728\u5f53\u4eca\u5feb\u8282\u594f", "\u4e0d\u4ec5\u4ec5\u662f", "\u800c\u662f", "\u7efc\u4e0a\u6240\u8ff0",
             "\u503c\u5f97\u4e00\u63d0\u7684\u662f", "\u5728\u8fd9\u4e2a\u65e5\u65b0\u6708\u5f02", "\u5168\u9762\u63d0\u5347",
             "\u8d4b\u80fd", "\u624b\u63e1\u624b", "\u6253\u9020\u95ed\u73af"]
OPENERS = ["Moreover", "Furthermore", "In conclusion", "Additionally", "Overall"]

def check(t):
    low = t.lower()
    hits = []
    for w in BANNED + CN_BANNED:
        if w.lower() in low:
            hits.append(("\u7981\u8bcd", w))
    for o in OPENERS:
        if re.search(r"(^|[.!?]\s+)" + o + r"\b", t):
            hits.append(("\u8fde\u63a5\u8bcd\u5f00\u5934", o))
    sents = [s.strip() for s in re.split(r"[.!?\u3002\uff01\uff1f]+", t) if s.strip()]
    if len(sents) >= 6:
        n = len(sents)
        avg = sum(len(s) for s in sents) / n
        var = sum((len(s) - avg) ** 2 for s in sents) / n
        if var < 40:                       # 句\u957f\u592a\u5747\u5300 = 机\u5668\u5473
            hits.append(("\u53e5\u957f\u592a\u5747", "var=%.1f" % var))
        if len(t.split()) > 0 and t.count(",") / max(1, n) > 1.5:
            hits.append(("\u9017\u53f7\u5bc6\u96c6", "\u6bcf\u53e5 %.1f \u4e2a" % (t.count(",") / n)))
    return hits

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file"); ap.add_argument("--text")
    a = ap.parse_args()
    t = open(a.file, encoding="utf-8", errors="replace").read() if a.file else (a.text or "")
    hits = check(t)
    if not hits:
        print("AI \u5473\u68c0\u67e5\uff1a\u672a\u547d\u4e2d\uff08\u8bcd\u8868 0 \u00b7 \u53e5\u957f\u6709\u8d77\u4f0f\uff09")
        return 0
    print("AI \u5473\u68c0\u67e5\uff1a\u547d\u4e2d %d \u5904" % len(hits))
    for k, v in hits[:12]:
        print("   [%s] %s" % (k, v))
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
