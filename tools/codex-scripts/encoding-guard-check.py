# -*- coding: utf-8 -*-
"""编码守门审查 —— **不带 -X utf8 调用时不许静默输出空**（主人令 2026-10-10 起）

由来（一手账，2026-10-10 一天里撞了三次）：
  同一个病咬掉了开机自检的 3 条红，每次都长一个样：
    测试/判据调工具用的是 [sys.executable, TOOL, ...] —— **不带 -X utf8**；
    而本机控制台编码是 **GBK**；工具用 ensure_ascii=False 印到非 ASCII（尤其 U+21D2 那个箭头）时抛
        UnicodeEncodeError: 'gbk' codec can't encode character U+21D2
    ⇒ **stdout 是空的** ⇒ 调用方 json.loads/解析空 ⇒ 判据恒红。
  实测对照（cloud-config-wiring.py，同一次运行）：
    不带 -X utf8 ⇒ rc=1 / stdout **0** 字节 / stderr 528
    带   -X utf8 ⇒ rc=0 / stdout 755 字节 / stderr 0

为什么这不是小事：**它不报错，它只是空**。空会让调用方当「没结果」，
而「没结果」与「结果就是空」在全仓口径里是两件事。
  · 全仓扫描：tools/codex-scripts 下会印非 ASCII 的 .py 里
      **已有 UTF-8 守门 307 件 · 没有守门 143 件**（本件写的时候的数）。

## 判据（**棘轮**，不是恒红 —— 恒红的判据等于死判据）
  ① 基线（state/encoding-guard-baseline.json）里**没有**的件，
     如果会印非 ASCII 又没守门 ⇒ 🔴 红（**新件不许再犯**）
  ② 基线里**已经修好**的件 ⇒ 提示「可以移出基线」（**不算红**，
     但要报 —— 不报的话基线永远不会缩，棘轮就成了摆设）
  ③ 负控（真植入）：往临时目录塞一个会印非 ASCII、又没守门的新件 ⇒ 必须红
  ④ **源码解析门**（2026-10-17 补 · 见下）：任何 .py **编不动** ⇒ 🔴 红，且**不接受基线豁免**

## ④ 为什么必须补「解析门」（一手事故，2026-10-17）
  我（AI）当天用 `bash <<'PY'` 给 `sweep-db.py` / `tentacle-browser-session.py` 补守门，
  Git Bash 把 python 字符串里的 `\\n` 转成了**字面 `/n`** ⇒ 两个文件从那次提交起就是
  `SyntaxError: invalid syntax`（`try:/n        _s.reconfigure(...)`）。
  **本判据当时报的是 ✅ 无新增违规** —— 因为 `_has_guard()` 是纯文本查：
  只要源码里同时出现 `reconfigure` 与 `encoding` 就算「有守门」，哪怕那一行根本编不动。
  ⇒ 「守门字符串在」≠「文件是活的」。补 ④：**编不动 = 比没守门更坏**，一律红。
  这也解释了为什么它当时一路假绿：字节数都没变（`/n` 2 字节 → CRLF 2 字节）。

## 什么算「有守门」
  源码里出现 stdout/stderr 的 reconfigure(encoding=...) 或等价写法。

## 什么算「会印非 ASCII」
  源码里出现大于 U+007F 的字符（中文、箭头、emoji、✅🔴 都算）。
  口径从宽：**宁可多算一个**，也不放过一个会静默变空的件。

用法: py -3.14 -X utf8 tools/codex-scripts/encoding-guard-check.py [--root 目录] [--json] [--selftest]
退出码：0 = 无新增违规且全部可解析；1 = 有新增违规或有编不动的件；3 = 不适用。
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")   # type: ignore[attr-defined]
    except Exception:
        pass

WS = pathlib.Path(__file__).resolve().parents[2]
BASELINE = WS / "state" / "encoding-guard-baseline.json"
SCAN_ROOT = WS / "tools" / "codex-scripts"


def _has_guard(text: str) -> bool:
    """有没有把 stdout/stderr 钉成 UTF-8。"""
    return ("reconfigure" in text and "encoding" in text) or "PYTHONIOENCODING" in text


def _prints_non_ascii(text: str) -> bool:
    """源码里有非 ASCII 字符（中文/箭头/emoji/✅🔴 都算）。口径从宽。"""
    return any(ord(c) > 127 for c in text)


def _parses(text: str) -> bool:
    """这个文件**编不编得动**（判据 ④）。

    为什么与 `_has_guard` 分开：`_has_guard` 是纯文本查，守门那一行**本身写坏了**它照样认。
    2026-10-17 实测：两个文件的 `try:/n        _s.reconfigure(...)` 是语法错误，
    而本判据报 ✅ —— 守门字符串在，文件却是死的。
    """
    try:
        ast.parse(text)
        return True
    except SyntaxError:
        return False


def scan(root=None, pattern="*.py"):
    root = pathlib.Path(root or SCAN_ROOT)
    if not root.is_dir():
        return None
    rows = {}
    for f in sorted(root.rglob(pattern)):
        if any(part in ("__pycache__", ".git") for part in f.parts):
            continue
        try:
            t = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not _prints_non_ascii(t):
            continue
        rel = str(f.relative_to(root)).replace(chr(92), "/")
        rows[rel] = {"guarded": _has_guard(t), "parses": _parses(t), "bytes": len(t)}
    return rows


def read_baseline(path=None):
    f = pathlib.Path(path or BASELINE)
    if not f.is_file():
        return set()
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return set()
    if isinstance(d, dict):
        return set(d.get("known_unguarded") or [])
    return set(d or [])


def judge(rows, baseline):
    """返回 (新增违规, 已修好可移出基线, 编不动的件)。

    **编不动的件单列一档、不吃基线**：基线是给「存量没守门」留的台阶，
    不是给「文件是死的」发的免死牌。
    """
    new_bad, fixed, broken = [], [], []
    for rel, info in (rows or {}).items():
        if not info.get("parses", True):
            broken.append(rel)
            continue
        if info["guarded"]:
            if rel in baseline:
                fixed.append(rel)
            continue
        if rel not in baseline:
            new_bad.append(rel)
    return sorted(new_bad), sorted(fixed), sorted(broken)


def render(rows, baseline, new_bad, fixed, broken):
    print("=" * 74)
    print("编码守门审查 —— 不带 -X utf8 调用时不许静默输出空")
    print("=" * 74)
    total = len(rows or {})
    guarded = sum(1 for v in (rows or {}).values() if v["guarded"])
    print("  扫了 %d 件会印非 ASCII 的 .py" % total)
    print("    已有守门 %d 件 · 没有守门 %d 件" % (guarded, total - guarded))
    print("  基线登记存量 %d 件" % len(baseline))
    print("")
    if broken:
        print("  🔴 **源码解析不了**（编都编不动 —— 比没守门更坏，基线也不豁免）—— %d 件" % len(broken))
        for r in broken[:20]:
            print("      " + r)
        print("")
        print("      常见原因：heredoc 里把 `\\n` 写成了字面 `/n`（2026-10-17 真踩坏两件，")
        print("      而且字节数没变，所以连大小都对得上）。修法：把那两处换回真换行。")
    if new_bad:
        print("  🔴 **新增违规**（基线里没有、又会印非 ASCII、又没守门）—— %d 件" % len(new_bad))
        for r in new_bad[:20]:
            print("      " + r)
        print("")
        print("      修法：在入口加")
        print("        for _s in (sys.stdout, sys.stderr):")
        print("            _s.reconfigure(encoding=chr(34)+chr(117)+chr(116)+chr(102)+chr(45)+chr(56)+chr(34))")
        print("        （本仓已有 307 件这么做）")
    else:
        print("  ✅ 无新增违规（新件没有再犯这个病）")
    if fixed:
        print("")
        print("  ➖ 已修好、可以移出基线的 %d 件（不算红，但**要报**，否则棘轮不缩）：" % len(fixed))
        for r in fixed[:20]:
            print("      " + r)
    print("")


def selftest():
    import tempfile
    ok = []
    with tempfile.TemporaryDirectory() as td:
        d = pathlib.Path(td)
        # 🔴 样本里必须写**真箭头**（不是 chr(0x2192)）——
        #    因为本件的口径是【源码里有非 ASCII 字符】；写 chr(0x2192) 的源文本仍全是 ASCII，
        #    首跑就是这么自己把自己骗过去的（扫到 0 件 ⇒ 4 条自检全红）。
        _g = "import sys\n"
        _g += "sys.stdout.reconfigure(encoding=\"utf-8\")\n"
        _g += "print(\"→\")\n"
        (d / "guarded.py").write_text(_g, encoding="utf-8")
        (d / "unguarded.py").write_text("print(\"→\")\n", encoding="utf-8")
        (d / "ascii_only.py").write_text("print(1)\n", encoding="utf-8")
        # 判据 ④ 的负控样本：**守门字符串明明在**，但那两行编不动（真踩过的坏法）
        (d / "broken.py").write_text(
            "import sys\n"
            "for _s in (sys.stdout, sys.stderr):\n"
            "    try:/n        _s.reconfigure(encoding=\"utf-8\")\n"
            "    except Exception:/n        pass\n"
            "print(\"→\")\n", encoding="utf-8")
        rows = scan(d) or {}
        ok.append(("真件·扫到会印非 ASCII 的件", len(rows) == 3,
                   "扫到 %d 件（ascii_only 不算）" % len(rows)))
        ok.append(("真件·有守门的认成 guarded", rows.get("guarded.py", {}).get("guarded") is True, ""))
        nb, fx, bk = judge(rows, set())
        ok.append(("真植入负控·空基线下无守门件 ⇒ 必红", nb == ["unguarded.py"], "点名 %s" % nb))
        ok.append(("真件·有守门件不算违规", "guarded.py" not in nb, "点名 %s" % nb))
        ok.append(("真植入负控·守门字符串在但编不动 ⇒ 必红（判据④）",
                   bk == ["broken.py"], "点名 %s" % bk))
        ok.append(("真件·编不动的件不吃基线豁免", judge(rows, {"broken.py"})[2] == ["broken.py"],
                   "登记进基线后仍点名"))
        nb2, _, _ = judge(rows, {"unguarded.py"})
        ok.append(("真件·登记进基线后不再红（棘轮生效）", nb2 == [], "点名 %s" % nb2))
        _, fx2, _ = judge(rows, {"guarded.py"})
        ok.append(("真植入负控·基线里的件修好了 ⇒ 必报可移出", fx2 == ["guarded.py"], "报 %s" % fx2))
    bad = [n for n, c, _ in ok if not c]
    for n, c, d2 in ok:
        print("  %-46s %s  (%s)" % (n, "✅" if c else "❌", d2))
    print("")
    print("encoding-guard-check 自检: %s（%d 条）"
          % ("全部通过" if not bad else "%d 条失败" % len(bad), len(ok)))
    return 1 if bad else 0


def main():
    if "--selftest" in sys.argv[1:]:
        return selftest()
    args = sys.argv[1:]
    root = None
    if "--root" in args:
        i = args.index("--root")
        if i + 1 < len(args):
            root = args[i + 1]
    rows = scan(root)
    if rows is None:
        print("编码守门审查 · **不适用**（扫的目录不在）：%s" % (root or SCAN_ROOT))
        return 3
    baseline = read_baseline()
    new_bad, fixed, broken = judge(rows, baseline)
    render(rows, baseline, new_bad, fixed, broken)
    if "--json" in args:
        print(json.dumps({"new_bad": new_bad, "fixed": fixed, "broken": broken,
                          "total": len(rows), "baseline": len(baseline)},
                         ensure_ascii=False, indent=1))
    return 1 if (new_bad or broken) else 0


if __name__ == "__main__":
    raise SystemExit(main())
