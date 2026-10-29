# -*- coding: utf-8 -*-
"""静态交付件的**新鲜度**审计器 —— 三类判据，一件工具。

## 为什么静态件要单独一套判据

13 块面板分两类**根本不同**的东西：
  · 实时面板（4 块走 :8765 + 1 块构建期烘焙）⇒ 判「**数据连没连上**」（扰动法，见 `panel-connectivity.py`）
  · **静态交付件（6 块）** ⇒ 没有实时源，"连接"对它们**不适用**；
    该判的是「**内容是不是当前版本的**」

## 三类判据（**适用面不同，不许混用**）

① **上位版本行差** —— 适用：该件是**别的件的快照**（如 `deploy` 是 V22 的快照）。
   实测行差 vs 它自述的行差；吻合 ⇒ **自述被验证**。
② **时间关系** —— 页面落盘时间 vs 它所描述对象的最后改动。
   ⚠️ **本类只给线索、不给结论**：页面晚于对象 ≠ 页面内容还对；页面早于对象 ≠ 一定陈旧。
③ **内嵌硬断言逐条对** —— 页面里写的「`<精确路径>` · `<N> B`」是**可核的**：拿盘上此刻的字节数逐条对。
   **这一类最硬**，也是唯一能直接判「它引的读数还成不成立」的。

## 两轮踩出来的顺序纪律（写死不許反）

**先认准"它实际引了什么"，再谈对错。** 「它一般指哪儿」**不是判据**。
第 20 轮我按**自己列的**四个抽屉当"被描述对象" ⇒ 断言"04-cut 那格陈旧"；
第 21 轮 grep 一看，**那一页根本没引 04-cut** ⇒ 收回。
⇒ 所以本器**第②类里不许手写对象名单**，对象一律**从页面里捞**。

## 跑法

    py -3.14 tools/codex-scripts/static-freshness.py            # 跑下表全部
    py -3.14 tools/codex-scripts/static-freshness.py --page hitl
"""

import argparse
import difflib
import io
import re
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = next(p for p in Path(__file__).resolve().parents if (p / "gbt_allinone").is_dir())
T = ROOT / "projects" / "_shared" / "templates"

# id → (页面, ①的上位版本或 None)
PAGES = {
    "hitl": (T / "20260921-三方向-HITL1审批屏.html", None),
    "form": (T / "20260921-三方向-HITL1-分镜契约填写页.html", None),
    "deploy": (ROOT / "deploy" / "index.html", ROOT / "V22 GBT小土豆V8-可交互原型.html"),
}


def TS(p):
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(p.stat().st_mtime))


def crit3(text: str, page: Path) -> tuple:
    """③ 内嵌硬断言：`<code>projects/...</code> · N B` 逐条对。返回 (ok, bad, n)。"""
    pairs = re.findall(r"<code>(projects/[^<]+)</code>\s*·\s*(\d+)\s*B", text)
    ok = bad = 0
    for rel, n in pairs:
        p = ROOT / rel
        if not p.exists():
            print("      ❌ 盘上没有：%s（它说 %s B）" % (rel[-52:], n))
            bad += 1
        elif p.stat().st_size == int(n):
            print("      ✅ 逐字节吻合：%s（%s B）" % (rel[-52:], n))
            ok += 1
        else:
            print("      🔴 **对不上**：%s ｜ 说 %s B · 此刻 %d B（差 %+d）"
                  % (rel[-52:], n, p.stat().st_size, p.stat().st_size - int(n)))
            bad += 1
    return ok, bad, len(pairs)


def crit2(text: str, page: Path) -> None:
    """② 时间关系。⚠️ 对象**从页面里捞**（`<code>projects/...</code>`），**不许手写名单**。"""
    objs = sorted({m for m in re.findall(r"<code>(projects/[^<]+)</code>", text)})
    if not objs:
        print("      （页面里没捞到它引用的仓内路径 ⇒ 本类不适用）")
        return
    pm = page.stat().st_mtime
    print("      页面落盘 %s ｜ 它引了 %d 条仓内路径：" % (TS(page), len(objs)))
    for rel in objs:
        p = ROOT / rel
        if not p.exists():
            print("        · %s —— 盘上没有" % rel[-46:])
            continue
        newer = p.stat().st_mtime > pm
        print("        · %s —— 改动 %s %s"
              % (rel[-46:], TS(p), "🔴 **晚于页面**（该格读数可能是那一刻的快照）" if newer else "（早于页面）"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--page", default="")
    a, _u = ap.parse_known_args()
    want = [a.page] if a.page else list(PAGES)

    print("=" * 80)
    print("静态交付件 · 新鲜度审计（三类判据，适用面不同，不许混用）")
    print("=" * 80)
    hard_bad = 0
    for pid in want:
        page, upper = PAGES.get(pid, (None, None))
        if page is None or not page.exists():
            print("\n[%s] ❌ 页面不在盘上" % pid)
            continue
        text = io.open(page, encoding="utf-8", errors="replace").read()
        print("\n[%s] %s" % (pid, page.name))
        print("  ① 上位版本行差：", end="")
        if upper is None or not upper.exists():
            print("**不适用**（它没有可比的上位版本 —— 不许硬套）")
        else:
            dep = text.splitlines()
            oth = io.open(upper, encoding="utf-8", errors="replace").read().splitlines()
            d = list(difflib.unified_diff(oth, dep, lineterm="", n=0))
            add = sum(1 for x in d if x.startswith("+") and not x.startswith("+++"))
            dele = sum(1 for x in d if x.startswith("-") and not x.startswith("---"))
            print("vs %s → 增 %d · 删 %d · **合计 %d 行差**" % (upper.name, add, dele, add + dele))
        print("  ② 时间关系：")
        crit2(text, page)
        print("  ③ 内嵌硬断言（这一类最硬）：")
        ok, bad, n = crit3(text, page)
        hard_bad += bad
        if n == 0:
            print("      （本页没有「路径·字节」式硬断言 ⇒ 本类不适用；**不等于它没问题**）")
        else:
            print("      ⇒ 吻合 %d / 对不上 %d" % (ok, bad))

    print("\n" + "=" * 80)
    print("判读：③ 那一类**对不上 %d 条**。" % hard_bad)
    print("  · ③ 吻合   ⇒ 那一格引的读数**仍然成立**（**这是实证**）")
    print("  · ③ 对不上 ⇒ 页面确实陈旧（**这也是实证**）")
    print("  · ② 只给线索，**不给结论** —— 时间先后不能单独判对错")
    print("  · 本器**只测新鲜度，不判「该不该更新」** —— 那是主人的决定")
    return 1 if hard_bad else 0


if __name__ == "__main__":
    sys.exit(main())
