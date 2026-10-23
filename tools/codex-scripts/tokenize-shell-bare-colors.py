#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""把 `holo_pet_w3/window.css` 里**越出 token 块的裸色值**收进 `:root`（**视觉零变化**）。

由来（一手，2026-09-25）：
    `holo_pet_w3` 自己的测试套件（`npm test` → `node --test tests/test_*.cjs`）现读
    **76 条 · 75 过 · 1 红**：`test_brand_tokens.cjs` 第 4 条
    「裸色值纪律：:root 之外不许出现裸色值（§2.1 冻结约束）」。
    而这条纪律**就写在 `window.css` 第 2 行的文件头注释里**（"裸色值只允许出现在 §1 token 定义块里"）。
    ⇒ **纪律被声称了、也被断言了，但 14 行里 17 处没照做，而没人跑过那套测试。**

修法（两刀，**每一处都保持颜色值逐字不变** ⇒ 渲染结果零变化）：
  甲、**删掉多余的 `var()` 兜底**（`--gbt-panel` / `--gbt-cyan` 都已在 `:root` 里声明）：
        `var(--gbt-cyan, #00e5ff)` → `var(--gbt-cyan)`（6 处）
      ⚠️ `var(--gbt-mono, ui-monospace, monospace)` **不动** —— `--gbt-mono` **没在** `:root` 里，
         那个兜底是**必要的**，而且它不是裸色值。
  乙、把结构性半透明值（玻璃高光/发丝线/阴影）**收进 `:root`** 成新 token，再原地引用。

用法：
  python tools/codex-scripts/tokenize-shell-bare-colors.py            # dry-run
  python tools/codex-scripts/tokenize-shell-bare-colors.py --apply
退出码：0 = 无需改 或 已改；1 = dry-run 时仍待改；2 = 出错。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
CSS = ROOT / "holo_pet_w3" / "window.css"

# 新 token（**值逐字照原样**，只起名）—— 键=token 名，值=(字面量, 说明)
NEW_TOKENS = [
    ("--gbt-glass-hi", "rgba(255,255,255,.018)", "顶缘玻璃高光（极淡）"),
    ("--gbt-glass-zero", "rgba(255,255,255,0)", "玻璃渐隐终点"),
    ("--gbt-hairline", "rgba(255, 255, 255, .02)", "发丝分隔线"),
    ("--gbt-hairline-soft", "rgba(255, 255, 255, .012)", "更淡的发丝线"),
    ("--gbt-edge-hi", "rgba(255,255,255,.03)", "顶缘一道极细高光：说明它有厚度"),
    ("--gbt-tint-hover", "rgba(255, 255, 255, .03)", "悬停底色"),
    ("--gbt-shadow-contact", "rgba(4,8,20,.55)", "接触阴影"),
    ("--gbt-shadow-ambient", "rgba(4,10,28,.38)", "环境阴影"),
]

# 甲：删多余兜底（成对替换，逐字）
FALLBACK_FIX = [
    ("var(--gbt-cyan, #00e5ff)", "var(--gbt-cyan)"),
    ("var(--gbt-panel, rgba(10,15,32,.72))", "var(--gbt-panel)"),
]
# 乙：裸值 → token（**先长后短**，免得 `rgba(255,255,255,.03)` 被更短的规则吃掉）
LITERAL_FIX = [
    ("rgba(255,255,255,.018)", "var(--gbt-glass-hi)"),
    ("rgba(255,255,255,0)", "var(--gbt-glass-zero)"),
    ("rgba(255, 255, 255, .02)", "var(--gbt-hairline)"),
    ("rgba(255, 255, 255, .012)", "var(--gbt-hairline-soft)"),
    ("rgba(255,255,255,.03)", "var(--gbt-edge-hi)"),
    ("rgba(255, 255, 255, .03)", "var(--gbt-tint-hover)"),
    ("rgba(4,8,20,.55)", "var(--gbt-shadow-contact)"),
    ("rgba(4,10,28,.38)", "var(--gbt-shadow-ambient)"),
]


def main(argv) -> int:
    apply = "--apply" in argv
    css = CSS.read_text(encoding="utf-8")
    orig = css
    plan = []

    for old, new in FALLBACK_FIX:
        n = css.count(old)
        if n:
            plan.append("甲 · 删多余兜底 ×%d：%s → %s" % (n, old, new))
            css = css.replace(old, new)
    for old, new in LITERAL_FIX:
        # 只在 `:root` 块**之外**替换（块里的声明本身要保留字面量）
        open_i = css.index("{", css.index(":root"))
        close_i = css.index("}", open_i)
        # 🔴 **head 必须切到 open_i**，不是 close_i ——
        #    第一版写成 `head = css[:close_i]` 而 `body = css[open_i:close_i]`，
        #    于是 `head + body` **把 :root 块算了两遍**：每跑一轮就多一份 :root，
        #    8 轮下来 28,931 字符被写成 **258,857**（≈9 倍），而脚本自己毫无察觉、照样落盘。
        #    实测轨迹：28857 → 29754 → 31556 → 35151 → 42350 → 56747 → 85544 → 143153 → 258361。
        head, body, tail = css[:open_i], css[open_i:close_i], css[close_i:]
        n = tail.count(old)
        if n:
            plan.append("乙 · 裸值收 token ×%d：%s → %s" % (n, old, new))
            css = head + body + tail.replace(old, new)

    print("现读计划（%d 条）：" % len(plan))
    for p in plan:
        print("   · %s" % p)
    if not plan:
        print("无需改动。")
        return 0
    if not apply:
        print("\n（dry-run：加 --apply 才落盘）")
        return 1

    # 🔴 **落盘前的保命闸**：改了颜色名，长度只该微增；
    #    第一版把 :root 重复插了 8 次（28,931 → 258,857 字符）却照样写盘 ——
    #    ⇒ 现在长度差超阈值就**拒绝落盘**（宁可不动，也不写出一个 9 倍大的文件）。
    delta = len(css) - len(orig)
    if abs(delta) > 2000:
        print("\n🔴 改后长度异常（%d → %d，差 %+d）⇒ **拒绝落盘**" % (len(orig), len(css), delta),
              file=sys.stderr)
        return 2
    print("\n长度检查：%d → %d（差 %+d）✅" % (len(orig), len(css), delta))

    # 把新 token 插进 :root（插在 `--gbt-violet` 那行之后，品牌三色之后、状态四色之前）
    open_i = css.index("{", css.index(":root"))
    anchor = css.index("\n", css.index("--gbt-violet", open_i))
    block = "\n\n  /* 结构性半透明（R-XX 裸色值纪律：值照原样，只是起了名）*/"
    for name, val, why in NEW_TOKENS:
        block += "\n  %s: %s;%s/* %s */" % (name, val, " " * max(1, 30 - len(name) - len(val)), why)
    css = css[:anchor] + block + css[anchor:]
    CSS.write_text(css, encoding="utf-8")
    print("\n已落盘：%s（%d → %d 字符）" % (CSS, len(orig), len(css)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
