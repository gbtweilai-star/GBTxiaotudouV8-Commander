# -*- coding: utf-8 -*-
"""跨文件重复块 · 负对照 B（只有 P1-11：与 A 有同一坨 8 行）。

它自己**不该**命中其它规则 —— 这是为了证明 P1-11 是"跨文件"这一条在报，
而不是文件里别的毛病在报。
"""


def totals(rows):
    total = 0
    count = 0
    for row in rows:
        total += row.get("amount", 0)
        count += 1
    average = total / count if count else 0
    return total, count, average
