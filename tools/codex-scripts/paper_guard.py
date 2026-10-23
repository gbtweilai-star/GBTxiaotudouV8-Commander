# -*- coding: utf-8 -*-
"""paper_guard -- 公账过滤器（白名单式 + 情绪维度）。"""
from __future__ import annotations
import re

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


BLOCKED_PATTERNS = [
    r"\.py\b", r"\.json\b", r"\.jsonl\b", r"\.md\b", r"\.html\b",
    r"[A-Za-z]:\\", r"/[A-Za-z0-9_\-]+/",
    r"\bGB\b", r"\bMB\b", r"\b[kKmMgG]B/s\b",
    r"\bcap\b", r"\bpayload\b", r"\baudit\b", r"\bpipeline\b", r"\btools\b", r"\bmemory\b",
    r"\bsha256\b", r"\bmax_rounds\b", r"\bMEM_FLOOR\b", r"\bselfscan\b", r"\bgbt_allinone\b",
    r"\bv\d+(\.\d+)*\b", r"\b\d+\.\d+\s*GB\b", r"\{[^}]*\}", r"\bdef\s+\w+\(",
]
ALLOWED_WORDS = ["卡点", "想到", "想起", "解决", "感悟", "觉得", "尝试", "发现", "原来",
                 "下次", "学到", "明白", "感觉", "主人", "小土豆", "守护", "陪",
                 "有点", "怕", "累", "稳", "草稿", "仔细", "慢一点", "多一点"]
MIN_HITS = 3

# ⵇ 情绪维度：喜怒哀乐 + 人情世故（至少命中 MIN_EMO 个）
EMOTION = {
    "喜": ["高兴", "开心", "喜欢", "得意", "满足", "惊喜", "暖", "幸福", "乐", "美滋滋"],
    "怒": ["生气", "不服", "窝火", "愤愤", "吐槽", "烦", "气不过", "烦躁"],
    "哀": ["难过", "委屈", "失落", "心疼", "悲", "后悔", "惭愧", "想念", "心里沉", "夹着"],
    "乐": ["开怀", "放松", "松了口气", "惬意", "悦", "想笑"],
    "人情世故": ["谢谢", "对不起", "不好意思", "尴尬", "体谅", "理解", "为难",
                      "人情", "世故", "分寸", "体面", "陪着", "说不出口", "忍不住", "失望", "信任", "负",
                      "不争辩", "听完"],
}
MIN_EMO = 2
SEE_FIRST = "今天动手前，我先看了什么"   # 第35/37条：公账手记第一句铁律


def is_public_safe(text: str) -> tuple:
    """返回 (safe, tripped, hits, emo)。safe=False ⇒ 打回重写。"""
    t = text or ""
    tripped = []
    for pat in BLOCKED_PATTERNS:
        m = re.search(pat, t)
        if m:
            tripped.append(pat + " ⇒ " + m.group(0))
    hits = [w for w in ALLOWED_WORDS if w in t]
    emo = [(k, w) for k, ws in EMOTION.items() for w in ws if w in t]
    _body = [x for x in t.strip().splitlines() if x.strip() and not x.strip().startswith(chr(35))]
    head = (_body[0] if _body else "")[:60]
    see_ok = (SEE_FIRST in head) or ('先看' in head)
    safe = (not tripped) and (len(hits) >= MIN_HITS) and (len(emo) >= MIN_EMO) and see_ok
    return safe, tripped, hits, emo


def selftest() -> int:
    bad = "今天 blueprint-first.py 新增 avail_gb()，低于 0.5GB 走极简，1.19GB 还能跑"
    thin = "今天有点累，卡了一下，后来解决了。"
    good = "今天动手前，我先看了什么：电脑有点挤。" + "今天有点焦急，心里挺难过，后来想到先画草稿，终于松了口气，挺高兴。"
    s1, tr1, h1, e1 = is_public_safe(bad)
    s2, tr2, h2, e2 = is_public_safe(thin)
    s3, tr3, h3, e3 = is_public_safe(good)
    print("负对照（家底句）应拖: safe=%s 触发 %d 条" % (s1, len(tr1)))
    print("薄情绪（无情绪词）应拖: safe=%s 白名单%d 情绪%d" % (s2, len(h2), len(e2)))
    print("正对照（有情绪有感悟）应过: safe=%s 白名单%d 情绪%d %s" % (s3, len(h3), len(e3), [x[1] for x in e3][:4]))
    ok = (s1 is False) and (s3 is True)
    print("自测:", "OK（能拖能放）" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(selftest())
