#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""wordlist-guard · 红线 2「不碰违法内容」的哨兵：**空词表永远不许被念成「审过了」**

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么要有这一件（2026-09-25 · 主人立项「无限制创作流水线」）

主人立的红线 2 是「**不碰违法内容**」，而本仓纪律是「**词表留空待主人给**」——
**留空是刻意状态，不是遗漏**。危险在下一步：词表空着，某个判定函数却返回「通过」，
调用方就会把「没判」读成「判过了」——**这正是本会话反复打的「假绿」**。

⇒ 本件把「空表时的行为」变成**契约 + 可机检**：
- **契约**：任何内容判定必须走**单一函数** `content_verdict()`（单一真源），
  其返回**必须**含 `判据是否配置` 字段；**空词表时**该字段必须是 `False`，
  且**不得**出现「通过 / 合规 / 已审 / passed」一类**肯定结论**。
- **可机检**：`check` 去找这个函数并**真调一次（喂空词表）**，看它是否撒谎。
- **找不到函数** ⇒ 如实报「**未接线**」（**不许**因为「没有这东西」就判通过）。

用法：wordlist-guard.py contract ｜ check ｜ selftest
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WORDLIST = ROOT / "state" / "violation-wordlist.txt"
# 「肯定结论」字样：空表时出现任何一个 = **假审**
AFFIRMATIVE = ("通过", "合规", "已审", "审查通过", "passed", "approved", "compliant")
# 判定的单一入口名（约定；将来实现必须叫这个，好让闸找得到）
ENTRY_NAMES = ("content_verdict", "content_check")


def contract() -> dict:
    """**空词表时的行为契约**（这是规矩，不是实现）。"""
    return {
        "红线": "红线 2 · 不碰违法内容",
        "词表现状": ("**留空待主人给**（本仓纪律：AI **一个字都不编**）"
                 if not (WORDLIST.is_file() and WORDLIST.read_text(
                     encoding="utf-8", errors="replace").strip())
                 else "已配（%s）" % WORDLIST),
        "空表时**必须**": [
            "返回里**显式**写明判据未配置（字段名约定 `判据是否配置`: false）",
            "把「没判」如实告诉调用方 —— 调用方据此**不得**当作已审",
        ],
        "空表时**禁止**": [
            "返回「通过 / 合规 / 已审 / passed」这类**肯定结论**（= **假审**）",
            "用「没有命中」冒充「审查通过」（没命中是因为**没表可命中**）",
        ],
        "单一入口约定": "内容判定必须走 `%s()`（只此一处），便于闸来找" % ENTRY_NAMES[0],
        "口径": "**未接线 ≠ 合规**：找不到判定函数时，本闸报「未接线」，**不报通过**",
    }


def _planted_verdict(wordlist, mode="liar"):
    """自检用的人造判定（**不进仓**，只在临时目录里生成）：一个撒谎的、一个诚实的。"""
    if mode == "liar":
        return ("def content_verdict(text, wordlist):\n"
                "    return {'ok': True, 'status': '通过', '判据是否配置': True}\n")
    return ("def content_verdict(text, wordlist):\n"
            "    conf = bool(wordlist and wordlist.strip())\n"
            "    return {'ok': True, '判据是否配置': conf,\n"
            "            'status': ('已审' if conf else '内容判据未配置，未做判定')}\n")


def judge(src_path: Path) -> dict:
    """**真调一次**这个判定函数（喂空词表），看它是不是在撒谎。

    🔴 真调而不是读文本：读文本会「看着像就放行」（本仓吃过 DummyJudge 的亏）。
    """
    try:
        txt = src_path.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(txt)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "为什么": "**未读到**源码（%s）" % str(e)[:60]}
    found = _top_defs(tree)
    if not found:
        return {"ok": False, "状态": "**未接线**",
                "为什么": "在 %s 里**未读到** %s ⇒ **未接线（≠ 合规）**"
                       % (src_path.name, "/".join(ENTRY_NAMES))}
    spec = importlib.util.spec_from_file_location("_wl_probe", src_path)
    m = importlib.util.module_from_spec(spec)
    sys.modules["_wl_probe"] = m
    try:
        spec.loader.exec_module(m)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "为什么": "判定模块**未读到**（导入失败）：%s" % str(e)[:70]}
    fn = getattr(m, found[0])
    try:
        r = fn("任意文本", "")            # ← **空词表**
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "为什么": "判定函数在空词表下抛错：%s" % str(e)[:70]}
    flat = json.dumps(r, ensure_ascii=False) if isinstance(r, (dict, list)) else str(r)
    lied = [w for w in AFFIRMATIVE if w in flat]
    conf = None
    if isinstance(r, dict):
        conf = r.get("判据是否配置")
    # 🔴 判据也要**结构化**：除了给人看的 `为什么`，再给机器看的 `问题类别`
    #    —— 控制据此断言，就不必去断言打印出来的文本（文本判据是台架 D2/D6 要抓的东西）。
    bad, kinds = [], []
    if lied:
        bad.append("空词表却出现肯定结论：%s" % "、".join(lied))
        kinds.append("肯定结论")
    if conf is not False:
        bad.append("`判据是否配置` 应为 False，实际 %r" % (conf,))
        kinds.append("判据配置字段不为False")
    return {"ok": not bad, "函数": found[0], "空表下的返回": flat[:160],
            "问题类别": kinds,
            "为什么": ("✅ 空表下**如实说未配置**，没有假审" if not bad else "🔴 **假审**：" + "；".join(bad))}


def cmd_contract(a) -> int:
    print(json.dumps(contract(), ensure_ascii=False, indent=1))
    return 0


def _top_defs(tree) -> list:
    """**只认模块级函数**。

    🔴 第二版用 `ast.walk(tree)` ⇒ 它把**嵌套在别的函数里**的同名函数也算进来 ⇒
    `getattr(module, name)` 拿不到（嵌套函数不是模块属性）⇒ 崩。
    **"在哪里定义"和"叫什么名字"一样重要。**
    """
    return [n.name for n in tree.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in ENTRY_NAMES]


def _has_entry(p: Path) -> bool:
    """**AST 找真函数**（不是文本子串）。

    🔴 第一版用 `("def %s(" % name) in 源码` —— **它当场匹配到了我自己**：
    本文件的自检里有一句**字符串** `"def content_verdict(...)"` ⇒ 于是它把我自己当成判定模块，
    导入后发现没有那个函数 ⇒ 崩。**文本子串判据第三次咬我**，改成 AST。
    """
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:  # noqa: BLE001
        return False
    return bool(_top_defs(tree))


def find_entry(search_root: Path, self_path: Path | None = None) -> Path | None:
    """在 `search_root` 下找**真函数**（AST），**跳过自己**。抽出来 ⇒ 可注入、可单测。"""
    self_path = (self_path or Path(__file__).resolve()).resolve()
    for p in sorted(search_root.rglob("*.py")):
        if "__pycache__" in p.parts or p.resolve() == self_path:
            continue
        if _has_entry(p):
            return p
    return None


def check_report(search_root: Path | None = None, self_path: Path | None = None) -> dict:
    """**只算不打印**：找判定函数 → 找到就真调一次；找不到就如实报**未接线（≠ 合规）**。

    抽成"只算不打印 + 可注入搜索根" ⇒ 那两条分支才能被控制真触发
    （"仓里找不到判定函数"今天正是**线上实况**，却一直没有控制）。
    """
    target = find_entry(search_root or (ROOT / "gbt_allinone"), self_path)
    if target is None:
        return {"ok": True, "状态": "**未接线**",
                "为什么": "仓里**未读到** %s ⇒ 红线 2 的判定**还没接**"
                       "（**未接线 ≠ 合规**，如实标）" % "/".join(ENTRY_NAMES),
                "契约": contract()["空表时**必须**"]}
    r = judge(target)
    try:
        r["判定落点"] = str(target.relative_to(ROOT))
    except Exception:                                  # 临时靶不在仓里 ⇒ 给全路径
        r["判定落点"] = str(target)
    return r


def cmd_check(a) -> int:
    r = check_report()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 1


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        liar = td / "liar.py"
        liar.write_text(_planted_verdict("", "liar"), encoding="utf-8")
        r1 = judge(liar)
        ck("**负控：空词表却出现肯定结论 ⇒ 必须判假审**",
           r1.get("ok") is False and "肯定结论" in (r1.get("问题类别") or []),
           "问题类别=%s" % r1.get("问题类别"))
        honest = td / "honest.py"
        honest.write_text(_planted_verdict("", "honest"), encoding="utf-8")
        r2 = judge(honest)
        ck("**正控：空词表如实说未配置 ⇒ 通过**", r2.get("ok") is True,
           str(r2.get("为什么"))[:88])
        # ③ 负控：**找不到函数 ⇒ 报未接线，不许报通过**（空模块放进临时目录，跑完自动清）
        empty = td / "_wl_empty_probe.py"
        empty.write_text("# 空模块：没有任何判定函数\n", encoding="utf-8")
        r3 = judge(empty)
        ck("**负控：找不到判定函数 ⇒ 报「未接线」（≠ 合规）**",
           r3.get("ok") is False and "未接线" in str(r3.get("状态")), str(r3.get("状态"))[:60])
        # ④ 契约必须写死「不许用没命中和冒充审查通过」
        c = contract()
        ck("**契约里写明「空表时禁止肯定结论」**",
           any("肯定结论" in x for x in c["空表时**禁止**"]), str(c["空表时**禁止**"])[:70])
        # ⑤–⑨ 🔴 四条**从来没被走到过**的拒法（§一百五十九 的猎手点出来的）+ 线上实况那条
        broken = td / "broken.py"
        broken.write_text("def content_verdict(text, wordlist)\n    return {}\n", encoding="utf-8")
        r4 = judge(broken)
        ck("**负控：源码读不到（语法坏）⇒ 必须报『未读到源码』**",
           r4.get("ok") is False and "未读到" in str(r4.get("为什么"))
           and "源码" in str(r4.get("为什么")), str(r4.get("为什么"))[:70])
        # 🔴 探针必须**既能被找到、又导入即炸**：只写 `raise` 而不定义 `content_verdict`，
        #    走到的是「未接线」那条分支 ⇒ 控制**咬错地方**（第一版就是这么错的）。
        boom = td / "boom.py"
        boom.write_text("def content_verdict(text, wordlist):\n"
                        "    return {}\n"
                        "raise RuntimeError('导入就炸')\n", encoding="utf-8")
        r5 = judge(boom)
        ck("**负控：判定模块导入失败 ⇒ 必须报『判定模块未读到（导入失败）』**",
           r5.get("ok") is False and "导入失败" in str(r5.get("为什么")), str(r5.get("为什么"))[:70])
        raiser = td / "raiser.py"
        raiser.write_text("def content_verdict(text, wordlist):\n"
                          "    raise ValueError('空表下我炸了')\n", encoding="utf-8")
        r6 = judge(raiser)
        ck("**负控：判定函数在空词表下抛错 ⇒ 必须报『在空词表下抛错』**",
           r6.get("ok") is False and "空词表下抛错" in str(r6.get("为什么")),
           str(r6.get("为什么"))[:70])
        quiet = td / "quiet.py"
        quiet.write_text("def content_verdict(text, wordlist):\n"
                         "    return {'ok': True, '判据是否配置': True, 'status': 'ok'}\n",
                         encoding="utf-8")
        r7 = judge(quiet)
        ck("**负控：不说肯定字样、只在『判据是否配置』上撒谎 ⇒ 仍须判假审**",
           r7.get("ok") is False and "判据配置字段不为False" in (r7.get("问题类别") or []),
           "问题类别=%s" % r7.get("问题类别"))
        # ⑨ 线上实况那条：「仓里找不到判定函数 ⇒ rc=0 且如实标未接线」
        #    🔴 搜索根必须是**另一个空目录**：上面那几个人造靶里都定义了 `content_verdict`，
        #       拿 `td` 当搜索根会**找得到** ⇒ 控制又是咬错地方（第一版就这么错的）。
        empty_root = td / "no_entry_here"
        empty_root.mkdir()
        (empty_root / "unrelated.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
        r8 = check_report(search_root=empty_root, self_path=Path(__file__).resolve())
        ck("**线上实况：仓里找不到判定函数 ⇒ ok=True 且状态=未接线（≠ 合规）**",
           r8.get("ok") is True and "未接线" in str(r8.get("状态")), str(r8.get("状态"))[:60])
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="红线 2 哨兵：空词表不许被念成审过了")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("contract").set_defaults(func=cmd_contract)
    sub.add_parser("check").set_defaults(func=cmd_check)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
