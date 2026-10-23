# -*- coding: utf-8 -*-
"""跨文件重复块 · 负对照 A（P1-11）+ 中文叙述性注释（P1-9）。

本文件与 `code-taste-cross-b.py` 中间那 8 行**逐行相同** —— 专门用来证明
「跨文件重复块」这条判据在干活（第二轮补的缺口 2）。
"""


def totals(rows):
    total = 0
    count = 0
    for row in rows:
        total += row.get("amount", 0)
        count += 1
    average = total / count if count else 0
    return total, count, average


def create_user(name):
    # 创建用户
    user = create_user_record(name)
    return user


def create_user_record(name):
    return {"name": name}
