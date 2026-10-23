"""中文串内层 ASCII 引号修整（**默认 dry-run**）—— 把反复犯的那个错变成一条命令。

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有它
「中文文案里写了 ASCII 引号」这个错，**本会话我犯了 11 次**（每次代价：语法错 → 停下 → 手改 → 重跑）。
`lint_cjk_quotes.py` 只**报**，不修；而人工修一次就得再赌一次手不抖。

## 它怎么判（宁窄不宽）
某个 `"` 的**左右两侧都是中日韩字符/中文标点** ⇒ 它是"文案里的内层引号"，
按出现顺序**成对**换成 「 」。**代码里真正的字符串定界符**（左邻是 `: ( , =`、右邻是空格/英文）**一律不动**。

## 🔴 它不动什么
- 不动 ASCII 引号的**定界符**（只换"内层"那一对）；
- **默认不写盘**（dry-run）；要写必须显式 `--write`，写盘用**字节**（不翻换行）。

用法：
  python tools/codex-scripts/fix-cjk-quotes.py scan [--roots tools/codex-scripts,gbt_allinone]
  python tools/codex-scripts/fix-cjk-quotes.py scan --write        # 真改（改完自己跑 py_compile + lint）
  python tools/codex-scripts/fix-cjk-quotes.py selftest
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROOTS = ("tools/codex-scripts", "gbt_allinone")
CJK = re.compile(r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]")
_SKIP = ("__pycache__", "vendor", ".git")

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def fix_line(line: str) -> tuple[str, int]:
    """**纯函数**（好上负控）：把"两侧都是中文"的那对内层引号换成「」。

    返回 (新行, 换了几处)。**奇数个命中 ⇒ 整行不动**（只换 0 处）：
    实测有这种形状 —— 开引号两侧是中文、闭引号后面跟着 `**` ⇒ 只换开的那一半会**把文案改坏**
    （`「我看过了"`）。**宁可不改，也不改一半。**
    """
    idx = [i for i, ch in enumerate(line)
           if ch == '"' and 0 < i < len(line) - 1
           and CJK.match(line[i - 1]) and CJK.match(line[i + 1])]
    if not idx or len(idx) % 2:
        return line, 0
    out, n = [], 0
    for i, ch in enumerate(line):
        if i in idx:
            out.append("「" if n % 2 == 0 else "」")
            n += 1
        else:
            out.append(ch)
    return "".join(out), len(idx)


def odd_lines(src: str) -> list:
    """**只报不改**：命中数为奇数的行（成不了对 ⇒ 人工看）。"""
    rows = []
    for i, ln in enumerate(src.splitlines(), 1):
        idx = [j for j, ch in enumerate(ln)
               if ch == '"' and 0 < j < len(ln) - 1
               and CJK.match(ln[j - 1]) and CJK.match(ln[j + 1])]
        if idx and len(idx) % 2:
            rows.append({"行": i, "命中": len(idx), "原文": ln.strip()[:80]})
    return rows


def scan_text(src: str) -> dict:
    rows = []
    for i, ln in enumerate(src.splitlines(), 1):
        new, n = fix_line(ln)
        if n:
            rows.append({"行": i, "换了几处": n, "原": ln.strip()[:70], "后": new.strip()[:70]})
    return {"命中行数": len(rows), "命中处数": sum(r["换了几处"] for r in rows), "逐行": rows[:8]}


def cmd_scan(roots: list[str], write: bool, only: str | None = None) -> int:
    """`only`（单件模式）：只处理这一个文件 —— 第 12 次踩坑时缺的就是它（当时只能手改）。"""
    files, rows, unread = 0, [], []
    if only:
        targets = [Path(only) if Path(only).is_absolute() else ROOT / only]
        if not targets[0].is_file():
            print("**未读到** %s ⇒ 拒" % only)
            return 2
        victims = [t for t in targets]
    else:
        victims = []
        for rel in roots:
            base = ROOT / rel
            if not base.is_dir():
                unread.append(rel)
                continue
            for p in sorted(base.rglob("*.py")):
                # 🔴 `store/` 是**数据区**（里面还有权限受限的目录，实测 PermissionError）；
                #    本工具是改**源码**的，不去碰数据区 —— 与署名守卫的 `_is_data()` 同口径。
                if any(s in p.parts for s in _SKIP) or p.name.startswith("_"):
                    continue
                if "store" in p.parts:
                    continue
                victims.append(p)
    for p in victims:
        try:
            src = p.read_text(encoding="utf-8", errors="replace")
        except Exception:                       # 🔴 读不开 ⇒ 进「未读到」，不静默丢
            unread.append(str(p.relative_to(ROOT)) if str(p).startswith(str(ROOT)) else str(p))
            continue
        # 🔴 这一段原来被缩进到了 `except` 里（等于"只有读不开才扫"）—— 单件模式当场报 0 命中，
        #    而 selftest 只测 fix_line/scan_text，**看不见**。⇒ 现在加了 `cmd_scan` 的控制。
        r = scan_text(src)
        odd = odd_lines(src)
        if not r["命中行数"] and not odd:
            continue
        files += 1
        rows.append({"文件": str(p.relative_to(ROOT)) if str(p).startswith(str(ROOT)) else str(p),
                     "命中行": r["命中行数"], "命中处": r["命中处数"], "奇数行（不改）": len(odd)})
        if write:
            # `keepends=True` ⇒ 每行自带换行，join 回去**逐字节复原**未改动的行
            # （第一版还去判断"最后一行有没有换行"，被台架 D7「位置型判据」点名 —— 点得对：
            #  那一judgement本来就不需要，去掉更准）
            p.write_bytes("".join(fix_line(ln)[0] for ln in src.splitlines(keepends=True))
                          .encode("utf-8"))
    total = sum(r["命中处"] for r in rows)
    print("命中 %d 处 · 涉及 %d 个文件 · %s"
          % (total, files, "已写盘" if write else "**dry-run（没写盘）**"))
    for r in rows[:20]:
        print("  %-46s 行 %-3d 处 %d" % (r["文件"], r["命中行"], r["命中处"]))
    if unread:
        print("**未读到（读不开的件）**：%s" % ("、".join(unread[:6])))
    if write and files:
        print("⚠️ 改完必须自己跑：`python -m py_compile <文件>` + `lint_cjk_quotes.py` + 自检")
    return 0


def selftest() -> int:
    checks, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad = bad + (0 if cond else 1)
        checks.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    one = fix_line('    return "**未读到**（不拿"空串"顶替）"\n')
    ck("**正控：中文串里的内层引号 ⇒ 换成「」**",
       "「空串」" in one[0] and one[1] == 2, "换 %d 处" % one[1])
    code = fix_line('    d = {"ok": True, "path": path}\n')
    ck("**负控：代码定界符一律不动**", code[1] == 0 and code[0] == '    d = {"ok": True, "path": path}\n',
       "换 %d 处" % code[1])
    two = fix_line('    return "句子里有"甲"和"乙"两个字"\n')
    ck("**正控：一行两对 ⇒ 交替「」（不许都变开括号）**",
       "「甲」" in two[0] and "「乙」" in two[0], two[0].strip())
    odd = fix_line('    **不能靠"我看过了"**\n')
    ck("**负控：命中数为奇数 ⇒ 整行不动**（宁可不改，也不改一半）",
       odd[1] == 0 and odd[0] == '    **不能靠"我看过了"**\n', odd[0].strip()[:40])
    ck("**正控：odd_lines 能把奇数行报出来**",
       len(odd_lines('    **不能靠"我看过了"**\n')) == 1, "")
    comment = fix_line('    # 他说"这样"就行\n')
    ck("**正控：注释里的也修**", "「这样」" in comment[0], comment[0].strip())
    plain = fix_line("    x = 1\n")
    ck("**边界：无引号行 ⇒ 原样**", plain == ("    x = 1\n", 0), "")
    empty = fix_line("")
    ck("**边界：空行 ⇒ 原样**", empty == ("", 0), "")
    n = scan_text('a = "中"文"引号"\n')
    ck("**正控：scan_text 报得出行号与处数**",
       n["命中行数"] == 1 and n["命中处数"] == 2, str(n["命中处数"]))
    # 🔴 控制必须打到 `cmd_scan` 上（原来只测纯函数 ⇒ 单件模式的缩进错了都看不见）
    import tempfile as _tf

    with _tf.TemporaryDirectory() as tds:
        victim = Path(tds) / "v.py"
        victim.write_text('x = "中"文"引号"\n', encoding="utf-8")
        rc = cmd_scan([], False, str(victim))
        ck("**正控：单件模式能扫到命中**（rc=0 且不改盘）",
           rc == 0 and victim.read_text(encoding="utf-8") == 'x = "中"文"引号"\n',
           "dry-run 未改盘")
        rc = cmd_scan([], True, str(victim))
        ck("**正控：单件模式 --write 真的改对了**",
           rc == 0 and "「文」" in victim.read_text(encoding="utf-8"),
           victim.read_text(encoding="utf-8").strip())
        rc = cmd_scan([], False, str(Path(tds) / "nope.py"))
        ck("**边界：单件模式指到不存在的文件 ⇒ rc=2**", rc == 2, "rc=%d" % rc)
    print(json.dumps({"自检": {"条数": len(checks), "通过": len(checks) - bad, "不通过": bad},
                      "逐条": checks}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["scan", "selftest"])
    ap.add_argument("--roots", default=",".join(DEFAULT_ROOTS))
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--file", help="**单件模式**：只处理这一个文件（第 12 次踩坑时缺的就是它）")
    a = ap.parse_args()
    if a.cmd == "selftest":
        return selftest()
    return cmd_scan([x.strip() for x in a.roots.split(",") if x.strip()], a.write, a.file)


if __name__ == "__main__":
    raise SystemExit(main())
