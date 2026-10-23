# -*- coding: utf-8 -*-
r"""自检成色审计（selftest-audit）· 扫出**负对照只喂合成数据、从不真植入**的机检器。

## 为什么需要它（2026-10-10 真账）
我在 supersede-check.py 上连着抓到**两个反向缺口**：
  ① 「同功能两份」**整类是死代码**（真植入一对才证出来）
  ② 「指针仍指旧版」**文档说查 AGENTS.md、代码只查 .cmd**（真植入才证出来）
而这两处，它自带的四条负对照**一条都抓不到** —— 因为那些负对照喂的是**合成 dict**：
只测**分类器**，不测**扫描器**。==分类器再对，也照不出扫描器的洞。==

⇒ 本件把这条教训做成尺子：**逐件看它的负对照是"真植入"还是"纯合成"**。

## 分型（诚实说明：这是**形状**判据，不是语义判据）
   真植入  = 负对照那一段里**真的动了文件系统**（write_text/write_bytes/mkdir/写入）
             且**收尾还原**（unlink/rmdir/shutil/finally）
   纯合成  = 有负对照，但只用 dict/字符串喂进纯函数 ⇒ **照不到扫描/IO 层**
   无      = 连负对照都没有
**形状判据会误判**（例：真植入写在别处、或封装进 helper）⇒ 它的输出是**线索**，判不判要人复核。
本件自己也要有负对照（否则它就是又一个坏判据）。

用法：
  py -3.14 -X utf8 tools/codex-scripts/selftest-audit.py            # 表格
  py -3.14 -X utf8 tools/codex-scripts/selftest-audit.py --selftest  # 本件自己的负控
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCAN_DIR = ROOT / "tools" / "codex-scripts"
SKIP = ("selftest-audit.py", "criterion_bench.py", "supersede-check.py")

NEG_START = re.compile(r"(负对照|负控|negs\s*=|selftest|自检)", re.I)
IO_WRITE = re.compile(r"(write_text|write_bytes|mkdir|copyfile|shutil\.copy)")
IO_RESTORE = re.compile(r"(unlink|rmdir|shutil\.move|rmtree|finally)")
# 🔴 2026-10-10 自纠：**这一维才决定"喂数据够不够"**。
#    我第一版只按"有没有动文件系统"分型，于是把 forget-list-check.py 也标成"纯合成" ——
#    可它**有 13 条负对照**，条条对着真失败模式；它的 check() 吃的是**文本**、不碰盘
#    ⇒ **喂数据就是对的测法**。==判据比对象宽 = 假红，我又犯了一次。==
#    ⇒ 真正该问的是：**这件东西的"被测单元"是不是扫描器/IO？**
#       · 扫盘（rglob/glob/os.walk/iterdir/read_text 全库）⇒ 负控**必须真植入**，合成数据照不到扫描层
#       · 纯函数（吃文本/结构）      ⇒ 负控喂数据**本来就对**，不算缺口
SCANNER = re.compile(r"(rglob|\bglob\(|os\.walk|iterdir|walk\()")


def looks_like_checker(p: pathlib.Path) -> bool:
    n = p.name.lower()
    return p.suffix == ".py" and any(k in n for k in ("check", "selfcheck", "audit", "verify", "guard"))


def classify(p: pathlib.Path) -> tuple:
    """返回 (分型, 凭什么)。形状判据 —— 输出是线索不是判决。"""
    try:
        t = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:                                            # noqa: BLE001
        return "读不了", type(e).__name__
    if not NEG_START.search(t):
        return "**无**", "全件搜不到负对照/自检字样"
    m = NEG_START.search(t)
    tail = t[m.start():]
    has_w = bool(IO_WRITE.search(tail))
    has_r = bool(IO_RESTORE.search(tail))
    scans = bool(SCANNER.search(t))
    if has_w and has_r:
        return "真植入", "负控段里既动了文件系统、又有还原"
    if has_w and not has_r:
        return "真植入(没看到还原)", "动了文件系统但没找到 unlink/rmdir/finally"
    if scans:
        # 扫盘件 + 只喂数据 ⇒ **真缺口**（照不到扫描层）
        return "**纯合成(扫盘件·真缺口)**", "它扫文件系统，而负控只喂数据 ⇒ **照不到扫描层**"
    # 不扫盘（单元是纯函数/文本）⇒ 喂数据本来就对，**不算缺口**
    return "纯函数·喂数据即对", "不扫文件系统（单元吃文本/结构）⇒ 喂数据的负控就是对的测法"


def main() -> int:
    ap = argparse.ArgumentParser(description="自检成色审计")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    rows = []
    for p in sorted(SCAN_DIR.glob("*.py")):
        if p.name in SKIP or not looks_like_checker(p):
            continue
        kind, why = classify(p)
        rows.append({"件": p.name, "分型": kind, "凭什么": why})
    if a.json:
        print(json.dumps({"逐件": rows}, ensure_ascii=False, indent=1))
        return 0
    print("机检器 · 自检成色审计（**负对照是真植入还是纯合成**）")
    print("%-36s %-20s %s" % ("件", "负对照分型", "凭什么"))
    print("-" * 106)
    for r in rows:
        print("%-36s %-20s %s" % (r["件"][:34], r["分型"], r["凭什么"][:52]))
    from collections import Counter
    c = Counter(r["分型"] for r in rows)
    print()
    print("分型统计: " + " · ".join("%s %d" % (k, v) for k, v in c.most_common()))
    print("口径: **形状判据** —— 输出是线索不是判决；真植入也可能写在别处、被误判成纯合成。复核为准。")
    return 0


def selftest() -> int:
    """本件自己的负控：**造三份真代码，看分型对不对**（三种形状各一条）。"""
    import tempfile

    fails, n = [], [0]
    NL = chr(10)        # 行分隔现算 —— 免得源码里的转义在这条链路上被吃成真换行（我踩过）

    def c(name, got, want):
        n[0] += 1
        ok = (got == want)
        print("  %-60s %s" % (name, "✅" if ok else "❌ 期望 %s 得到 %s" % (want, got)))
        if not ok:
            fails.append(name)

    # 四格：纯函数喂数据（对） · 扫盘件喂数据（**真缺口**） · 真植入 · 无负控
    pure = NL.join(["def check(t):", "    return True", "# 负对照：合成数据",
                    "negs = [('x', 'y', classify({'a': []}))]", ""])
    gap = NL.join(["import pathlib", "def check():",
                   "    return list(pathlib.Path('.').rglob('*.py'))",   # ← 它扫盘
                   "# 负对照：只喂数据", "negs = [classify({'a': []})]", ""])
    live = NL.join(["import pathlib", "# 负对照：真植入", "def neg():",
                    "    p = pathlib.Path('tmp_probe.old')", "    try:",
                    "        p.write_text('x')", "    finally:", "        p.unlink()", ""])
    none = NL.join(["def check():", "    return True", ""])
    with tempfile.TemporaryDirectory() as td:
        for tag, body, want in (("纯函数", pure, "纯函数·喂数据即对"),
                                ("扫盘件只喂数据", gap, "**纯合成(扫盘件·真缺口)**"),
                                ("真植入", live, "真植入"),
                                ("无负控", none, "**无**")):
            f = pathlib.Path(td) / (tag + ".py")
            f.write_text(body, encoding="utf-8")
            c("分型·%s ⇒ %s" % (tag, want), classify(f)[0], want)
    print()
    print("selftest-audit 自检: %s（%d 条）"
          % ("**全部通过**" if not fails else "**%d 条失败**" % len(fails), n[0]))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(main())
