#!/usr/bin/env python
# gbt-capability: none
"""caps_called_audit「调用方判据」探针 —— **读原始文件文本**，两种口径对照。

⚠️ 这个脚本存在的理由之一，是它的**前两版都错了**，而错误的测量差点让我改坏代码。
   教训写在下面，谁改谁看：

   错误 v1（AST 派）：以为「AST 只看实参/字典键/比较操作数」更准。
       实测 82 个能力位判据不一致，**错的方向是反的** —— 它把大量合法的
       「名字清单」引用（如 `awesome_tools_index.py` 里 `["create","auto_switch",…]`）
       全杀掉 ⇒ 把**已接线误判成孤儿**。反方向的假读数同样是假读数。

   错误 v2（窄规则派）：以为「字符串必须整段等于名字」就够。
       实测**自相矛盾**：一次算出 0 个翻转、一次算出 54 个。
       根因在探针自己：它把 `caps_called_audit._code_only()` 的产物
       （**一个 token 一行**）再喂进 `tokenize`，必然抛错并落到 `except` 兜底，
       而那个兜底**只剥注释、不剥字符串** ⇒ 散文串又被算成命中。
       ⇒ **测量工具自己坏了，于是"结论"跟着漂。**

   本版：**直接读原始文件**，两种口径各自独立实现，不借道 `_code_only()`。

背景（要修的那个真缺陷）
------------------------
`caps_called_audit` 判「某能力位有没有真调用方」用的是**纯文本命中**：
剥掉注释、**保留字符串**，然后 `\b名字\b` 子串匹配。它的文档把这件事写成
「被引用（= **真接线**）」—— 那个等号是假的。确认的假阳性：

    gbt_allinone/security/redteam.py
        "steps": ["sec_scan（自有代码）", "sec_chain（利用链推演，只出图不执行）"]
    —— 一句给人看的说明文字，把**没有任何真调用方**的 `sec_chain` 判成"已接线"。

两种口径
--------
A（现行等效）：剥注释、留字符串 → `\b名字\b` 命中即算。
B（候选窄规则）：剥注释**和**字符串后仍是完整词 → 算；**或**存在整段等于该名字的字符串字面量。

用法
----
    python tools/codex-scripts/audit-caller-rule-probe.py
    python tools/codex-scripts/audit-caller-rule-probe.py --json out.json
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _strip(text: str, strings: bool) -> str:
    """剥注释；`strings=True` 时连字符串字面量一起剥。（失败时退回正则，且**同样剥字符串**。）"""
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                continue
            if strings and tok.type == tokenize.STRING:
                continue
            out.append(tok.string)
        return "\n".join(out)
    except Exception:  # noqa: BLE001
        s = re.sub(r"#.*", "", text)
        if strings:
            s = re.sub(r"\"\"\".*?\"\"\"|'''.*?'''|\"[^\"]*\"|'[^']*'", " ", s, flags=re.S)
        return s


def _exact_strings(text: str) -> set:
    """取出所有「整段字符串字面量」的值。"""
    vals = set()
    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type != tokenize.STRING:
                continue
            s = tok.string
            m = re.match(r"^[a-zA-Z]*('''|\"\"\"|'|\")", s)
            if m:
                q = m.group(1)
                vals.add(s[len(q):-len(q)])
    except Exception:  # noqa: BLE001
        pass
    return vals


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    from gbt_allinone.tools import caps_called_audit as cca

 # _candidate_files() 返回的是**绝对 WindowsPath**，不是相对字符串 ——
    #    这里显式归一成仓库相对路径（前两版探针就是在这里炸的）。
    files = []
    for p in cca._candidate_files():
        p = Path(p)
        try:
            raw = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        try:
            rel = str(p.relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            rel = str(p).replace("\\", "/")
        files.append((rel, raw))

    data = cca.run("audit")
    cur_map = {r["kind"]: r["callers"] for r in data["wired"]}
    kinds = sorted({r["kind"] for r in data["wired"]} | set(data["orphans"]) |
                   set(data["external_entries"]) | set(data["self_ref_only"]))

    print("语料: 读到原始文件 %d 个" % len(files))
    print("能力位: %d 个 | 现行 wired %d | orphans %d | external_entries %d"
          % (len(kinds), len(data["wired"]), len(data["orphans"]),
             len(data["external_entries"])))
    print()

    flips, shrunk = [], 0
    for kind in kinds:
        pat = re.compile(r"\b" + re.escape(kind) + r"\b")
        a_files, b_files = [], []
        for rel, raw in files:
            if kind in rel:          # 同名模块自己的提及不算（沿用现行口径）
                continue
            if rel.endswith(".py"):
                if pat.search(_strip(raw, False)):
                    a_files.append(rel)
                if pat.search(_strip(raw, True)) or (kind in _exact_strings(raw)):
                    b_files.append(rel)
            elif rel.endswith((".js", ".cjs")):
                if pat.search(raw):
                    a_files.append(rel)
                    b_files.append(rel)
        a, b = bool(a_files), bool(b_files)
        if a != b:
            flips.append({"kind": kind, "A_接线": a, "B_接线": b,
                          "现行调用方": cur_map.get(kind, []),
                          "A调用方": a_files, "B调用方": b_files})
        elif a and b and set(a_files) != set(b_files):
            shrunk += 1

    print("=== 判定翻转（A=现行等效 ，B=候选窄规则）：%d 个 ===" % len(flips))
    for f in flips:
        print("  %-24s %s -> %s" % (f["kind"],
                                    "接线" if f["A_接线"] else "孤儿",
                                    "接线" if f["B_接线"] else "孤儿"))
        print("      现行调用方: %s" % (f["现行调用方"] or "(无)"))
        print("      B 保留的  : %s" % (f["B调用方"] or "(无)"))
    print()
    print("判定不变、仅调用方名单变短：%d 个" % shrunk)
    print()
    print("⚠️ 结论提示（2026-09-25 实测）：6 个翻转里**只有 `sec_chain` 是确认的假阳性**，")
    print("   其余 5 个（agency_tentacles / brain_route / codex_status / mirror_scan / sec_scan）")
    print("   很可能是被误杀的**真引用** ⇒ 窄规则是「用假阴性换假阳性」，**不得直接上线**。")
    print("   要修得先定义「散文串」与「嵌在长串里的合法引用」的判据，那是改工具契约，需主人拍板。")

    if args.json:
        Path(args.json).write_text(
            json.dumps({"flips": flips, "shrunk": shrunk}, ensure_ascii=False, indent=1),
            encoding="utf-8")
        print()
        print("已写", args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
