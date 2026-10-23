#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""lint_cjk_quotes · 拦一类**我犯了 13 次**的错：在**中文串里用 ASCII 引号**

## 为什么会有这个 lint
本会话我反复写「`不是"被安全策略挡住"`」这种句子 —— 外层是双引号字符串，里层又用了 ASCII `"`，
**字符串当场截断 ⇒ SyntaxError ⇒ 连自检都跑不起来**（语法错到不了"自检红"，直接是"自检不存在"）。
光靠"改完先 py_compile"不够：**编译失败时我得先看懂报错，而这类报错在 GBK 控制台下经常是乱码**
（实测 `invalid syntax. Perhaps you forgot a comma?` + 花屏），定位一次要好几分钟。

## 判据（精确到几乎无误报）
一个 ASCII `"`，**左右紧邻的全是汉字** ⇒ 命中。
- 合法边界长这样：`A("中文")` —— 左引号左边是 `(`，右引号右边是 `)`，**不可能两侧都是汉字**
- 犯错的形状长这样：`不是"被` —— 左是「是」、右是「被」，**两侧都是汉字** ✓

## 用法
    py -3.14 tools/codex-scripts/lint_cjk_quotes.py <文件或目录...>
命中 ⇒ 打印 `文件:行:列` 与那一行，**退出码 1**（可直接当闸用）。
"""
from __future__ import annotations

import pathlib
import re
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

CJK = r"\u4e00-\u9fff\u3000-\u303f\uff00-\uffef"
PAT = re.compile(r"(?<=[%s])\"(?=[%s])" % (CJK, CJK))     # 左右都是汉字/中文标点的 ASCII 双引号
PAT_S = re.compile(r"(?<=[%s])'(?=[%s])" % (CJK, CJK))    # 单引号同理


def scan(path: pathlib.Path) -> list[tuple[int, int, str]]:
    """🔴 **只对"编译不过"的文件说话** —— 这是本器不误报的关键。

    第一版对所有 .py 一律扫「汉字夹 ASCII 引号」，结果 **298 个文件命中 1769 处**，
    绝大多数在**注释与 docstring** 里（那里 ASCII 引号**无害**），器变成噪音。
    而真正的判据是反过来的：**文件只要能编译过，就不可能把 `"` 留在双引号串里**
    （那样串早就断了）⇒ 所以只有**编译失败**的文件才需要这份定位。
    """
    hits = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        return hits
    try:
        compile(text, str(path), "exec")
        return hits                      # 编译过 ⇒ 没问题，一个字都不报
    except SyntaxError as e:
        ln = e.lineno or 0
        hits.append((ln, e.offset or 0, "SyntaxError: %s" % (e.msg or "")[:80]))
    for i, line in enumerate(text.splitlines(), 1):
        for m in list(PAT.finditer(line)) + list(PAT_S.finditer(line)):
            hits.append((i, m.start() + 1, line.strip()[:120]))
    return hits


def main() -> int:
    args = sys.argv[1:] or ["tools"]
    total, bad = 0, 0
    for a in args:
        p = pathlib.Path(a)
        files = ([p] if p.is_file() else
                 [q for q in p.rglob("*.py") if "__pycache__" not in str(q)])
        for f in files:
            total += 1
            hits = scan(f)
            for ln, col, line in hits:
                bad += 1
                print("%s:%d:%d  %s" % (f, ln, col, line))
    print("\n扫了 %d 个 .py ｜ 命中 %d 处" % (total, bad))
    if bad:
        print("改法：把串里的 ASCII 引号换成「」—— 本仓中文文案一律用「」，不用 ASCII 引号")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
