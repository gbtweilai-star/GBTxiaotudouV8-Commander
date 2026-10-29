# -*- coding: utf-8 -*-
"""令牌漂移 · **语境感知**判据（只读）。

为什么要有它：`anti-ai-slop.md` 的 P1 条目是「令牌块外裸 hex ≤ 12」。
但"令牌块外"这四个字太粗 —— 逐字数下来，被算进去的东西里有三类**根本不是漂移**：

  ① 调色板展示（`sw('#04070f','Void',...)`）—— 那一屏就是给你看颜色的，颜色就是内容；
  ② 颜色数据（`colors: {"glow_cyan": "#bffdfb"}`、`led('#3ddc97','健康')`）—— 是实参，不是样式；
  ③ 复合选择器令牌块（`:root,[data-theme="dark"]{}`）—— 它**就是**令牌块，
     只认纯 `:root` 的检查器会把它整个漏掉，反而报成"块外裸 hex"。

拿粗口径的数去改交付物，就会把 ① ② 当漂移清掉 —— 那是**为指标乱改**。
本判据按**语境**分类，只把真正的样式漂移计入，并把每一类都打印出来（不静默丢）。

用法：
  py -3.14 tools/codex-scripts/audit_token_context.py
  py -3.14 tools/codex-scripts/audit_token_context.py --cap 12 --json
退出码：0 = 样式漂移在阈值内 · 1 = 超阈值 · 2 = 参数/文件问题。
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents
            if (p / "holo_pet_w3").is_dir() and (p / "gbt_allinone").is_dir())
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 负向断言排除 HTML 实体：`&#8722;`（减号）`&#8962;`（房号）里也有"#+数字"。
# 上一版写的是 `(?<!&#)` —— **那是错的**：`#` 前面两个字符是 `X&` 而非 `&#`
# （`#` 就是匹配起点本身），该断言永远成立，实体根本没被排除。
# 反证测试当场抓到（期望「实体不算颜色」却仍出现在类别里）。正确写法是只看前一个字符。
HEX = re.compile(r"(?<!&)#[0-9a-fA-F]{3,8}\b")

TARGETS = [
    ("V21 GBT小土豆V8-无限画布.html", "无限画布"),
    ("V21 GBT小土豆V8-可交互原型.html", "可交互原型"),
]

# → 计入「真漂移」的两类：它们在浏览器里**可以用 var() 表达**，所以是漂移
DRIFT = {"样式表非令牌区", "行内样式字符串"}
# → 不计入的三类：它们是内容/数据/令牌定义本身
NOT_DRIFT = {"令牌块内定义", "调色板展示", "颜色数据/实参", "HTML 实体"}


def classify(text: str) -> dict:
    spans_style = [(m.start(), m.end()) for m in re.finditer(r"<style[^>]*>.*?</style>", text, re.S)]
    spans_script = [(m.start(), m.end()) for m in re.finditer(r"<script[^>]*>.*?</script>", text, re.S)]

    # 令牌块：选择器里**含** :root 或 [data-theme…] 的规则块（复合选择器也算！）
    tok_spans = []
    for m in re.finditer(r"([^{}]*\{)\s*([^{}]*?)\}", text):
        sel = m.group(1)
        if ":root" in sel or "data-theme" in sel:
            if re.search(r"--[\w-]+\s*:", m.group(2)):
                tok_spans.append((m.start(), m.end()))

    def zone(i: int) -> str:
        for a, b in tok_spans:
            if a <= i < b:
                return "令牌块内定义"
        for a, b in spans_style:
            if a <= i < b:
                return "样式表非令牌区"
        for a, b in spans_script:
            if a <= i < b:
                # script 里再分：调色板展示 / 行内样式字符串 / 颜色数据
                ls = text.rfind("\n", 0, i) + 1
                le = text.find("\n", i)
                line = text[ls: le if le > 0 else len(text)]
                if re.search(r"\bsw\s*\(", line):
                    return "调色板展示"
                if re.search(r"""["']?\s*[:=]\s*["']#""", line) and not re.search(
                        r"(style|css|background|color|fill|stroke)\s*[:=]", line, re.I):
                    return "颜色数据/实参"
                if re.search(r"(style|css|background|color|border|fill|stroke|shadow)\s*[:=]",
                             line, re.I):
                    return "行内样式字符串"
                if re.search(r"\b(led|dot|chip|badge|sw)\s*\(\s*['\"]#", line):
                    return "颜色数据/实参"
                return "行内样式字符串"
        # 走到这里说明不在任何已知区块里（例如标签属性区）。
        # 注意：**没有「HTML 实体」这一类** —— `&#8722;` 那种在 HEX 正则的
        # `(?<!&#)` 负向断言处就已经被排除，压根不会进分类器。
        # 上一版在这里留了个永远到不了的实体分支，是死代码，已删。
        return "其它"

    buckets: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for m in HEX.finditer(text):
        z = zone(m.start())
        buckets[z][m.group().lower()] += 1
    return {k: dict(v) for k, v in buckets.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=12, help="样式漂移去重上限（默认 12，取自 P1 条目）")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    rc = 0
    report = {}
    print("=" * 92)
    print("令牌漂移 · 语境感知判据（只读）")
    print("=" * 92)
    print(f"  阈值：**真样式漂移**去重 ≤ {a.cap}（调色板/数据/令牌定义不计入）")

    for rel, label in TARGETS:
        p = ROOT / rel
        if not p.is_file():
            print(f"\n  [{label}] 文件不存在：{rel}")
            rc = 2
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        b = classify(text)
        print(f"\n{'─' * 92}\n  {label}  ({rel} · {p.stat().st_size:,} B)\n{'─' * 92}")

        drift_uniq, drift_occ = set(), 0
        for zone in sorted(b, key=lambda z: -sum(b[z].values())):
            uniq = len(b[zone])
            occ = sum(b[zone].values())
            tag = "计入漂移" if zone in DRIFT else ("不计入" if zone in NOT_DRIFT else "未分类")
            mark = "!" if zone in DRIFT else " "
            print(f"   {mark} {zone:<14} 去重 {uniq:>3} · 出现 {occ:>4}   [{tag}]")
            if zone in DRIFT:
                drift_uniq |= set(b[zone])
                drift_occ += occ
                top = sorted(b[zone].items(), key=lambda x: -x[1])[:8]
                print(f"       高频: {top}")
            elif zone == "令牌块内定义":
                print(f"       令牌: {sorted(b[zone])}")
            elif zone == "调色板展示":
                print("       这是**有意为之的色彩展示**，颜色就是内容 —— 不是漂移")
            elif zone == "颜色数据/实参":
                print("       这是传给函数的颜色实参/数据，不是样式声明")

        verdict = "PASS" if len(drift_uniq) <= a.cap else "HIT"
        if verdict == "HIT":
            rc = max(rc, 1)
        print(f"\n   → 真样式漂移：去重 {len(drift_uniq)} 个 · 出现 {drift_occ} 次   **{verdict}**")
        if verdict == "HIT":
            print(f"      超阈值 {len(drift_uniq) - a.cap} 个。**要清的是这些**，"
                  f"不是上面那些不计入的。")
        report[label] = {"drift_distinct": sorted(drift_uniq), "drift_occurrences": drift_occ,
                         "verdict": verdict,
                         "zones": {z: {"distinct": len(v), "occurrences": sum(v.values())}
                                   for z, v in b.items()}}

    print(f"\n{'=' * 92}")
    print("说明：本判据与粗口径的差别就在于**分语境**。粗口径把调色板展示、指示灯实参、")
    print("      复合选择器令牌块一律算成「块外裸 hex」，照它去改 = 把有意为之的颜色当漂移清掉。")
    print(f"{'=' * 92}")
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=1))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
