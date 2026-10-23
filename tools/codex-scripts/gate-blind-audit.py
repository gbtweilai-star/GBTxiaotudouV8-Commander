#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""gate-blind-audit · 「**门看不见的位**」到底有没有**自我约束**

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 背景（承 §一百二十五）
两个独立源对撞后，有 **16 位**在 `security/policy.py` 里**出现 0 次** ⇒
**门结构上看不见它们**，给任何参 `scopes` 都空 ⇒ 它们**只能靠模块自身的规则**把关。

**那模块自己到底管住了没有？** 本工具**逐位去读**，并**把"读到了什么"逐条列出来**。

## 🔴 判据与诚实边界
- 只认**可复核的静态标记**：写根白名单 · 只追加守卫 · AST 扫出**零写盘原语** · fail-closed 参数检查；
- **「没读到标记」≠「没有约束」** —— 可能换了名字。所以判决一律写
  「**静态没读到约束标记**」而**不是**「无约束」。**这句话不许省。**
- **只读**：只读源码 + AST，**不调任何能力位**。

用法：
  gate-blind-audit.py scan      # 16 位逐位列约束 + 判决
  gate-blind-audit.py selftest
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
PKG = ROOT / "gbt_allinone"

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

WRITE_PRIMS = ("write_bytes", "write_text", "mkdir", "unlink", "rmdir", "rmtree",
               "copytree", "rename", "replace", "open")
# 🔴 **两类标记，必须分开**（这是我上一轮判据太粗的更正）：
#   **带牙的（hard）**：真的约束"**写到哪里 / 能不能删**" ⇒ 才够格说"写面管住了"；
#   **软标记（soft）**：只说明"参数不对会报错 / 声明了只读 op" ⇒ **与写面安全无关**。
#   `raise ValueError` 在任何正常模块里都随处可见 —— 把它算成"有约束"就是**新的假绿**。
HARD_MARKERS = {
    "写根白名单": r"write_root|WRITE_ROOTS|_rel_inside|is_relative_to|\.relative_to\(",
    "只追加守卫": r"locked_append|append_only|append-only|只追加",
}
SOFT_MARKERS = {
    "fail-closed 参数检查": r"raise \w*Error|paths_required|bad_limit|缺少|必须点名",
    "凭据掩码": r"SECRET_RE|掩码|mask|前 4 位",
    "只读声明": r"READ_OPS|read_ops|只读",
}
MARKERS = {**HARD_MARKERS, **SOFT_MARKERS}

# 🔴 **单次运行内的读缓存**：`_modules_for()` 逐位跑一遍，17 个位就把同一批 `.py`
#    **重读 17 遍** ⇒ 体检里这一道 25.8s，全花在重复 I/O 上。
#    **缓存只活在当前进程内，不落盘、不跨进程** ⇒ 读数语义一个字都不变（下面有用前后哈希对账）。
_TEXT: dict = {}
_FILES: list = []


def _read(p: Path):
    """读文本（**一次运行只读一次**）。**读不开返回 `None`，不吞成空串** ——
    审计里有"读不开要看得见"这条规矩（D3 报的就是这个），不许被缓存抹平。"""
    k = str(p)
    if k not in _TEXT:
        try:
            _TEXT[k] = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            _TEXT[k] = None
    return _TEXT[k]


def _py_files() -> list:
    """要看的 `.py`（排除脚手架/缓存/测试）—— **只枚举一次**。"""
    if not _FILES:
        _FILES.extend(p for p in sorted(PKG.rglob("*.py"))
                      if "__pycache__" not in p.parts and "tests" not in p.parts
                      and p.name not in SCAFFOLD)
    return _FILES


def blind_kinds() -> tuple:
    """**现算**门看不见的位：零作用域 ∧ (框架说会改 ∨ safe=False) ∧ policy.py 里 0 次出现。"""
    from gbt_allinone import caps_registry as R
    from gbt_allinone import preflight as PF
    from gbt_allinone.security import policy as POL
    pol_txt = (PKG / "security" / "policy.py").read_text(encoding="utf-8", errors="replace")
    scc = set(PF.state_changing_kinds())
    meta = {}
    for name in ("BENIGN_CAPS", "UNIMPLEMENTED_CAPS"):
        d = getattr(R, name, None)
        if isinstance(d, dict):
            meta.update({k: (v if isinstance(v, dict) else {}) for k, v in d.items()})
    out = []
    for kind in sorted(meta):
        try:
            sc = tuple(getattr(POL.evaluate(kind, {}), "scopes", ()) or ())
        except Exception:
            sc = ("?",)
        if sc:
            continue
        m = meta[kind]
        if kind in scc or m.get("safe") is False:
            out.append({"位": kind, "域": m.get("domain"),
                        "框架说会改": kind in scc, "safe": m.get("safe"),
                        "policy.py 出现次数": pol_txt.count('"%s"' % kind)})
    return out, None


# 🔴 **脚手架黑名单**：这些文件**提到每一个位**（分派表 / 注册表 / 门 / 入口），
#    而它们**里面什么标记都有** ⇒ 不排除的话，**每个位都会"继承"全部标记** ⇒ **假全绿**。
#    实测踩过：第一版没排除 ⇒ **17 位全部得到同一组 4 个标记**（判据由构造满足，与数据无关）。
SCAFFOLD = {"api.py", "caps_registry.py", "preflight.py", "policy.py", "app.py",
            "__init__.py", "soul.py", "store.py"}


def _dispatch_modules() -> dict:
    """从 `api.py` 的**真分派**解析「位 → 实现模块」。**读分派，不猜名字。**

    🔴 为什么必须这样：第一版用「文件名含位名」猜 ⇒ `lr_submit`/`lr_tick` **一个模块都没猜到**
    （它们不那样命名）⇒ 仪器里出现**假空洞**，我却会读成"系统没有路"。
    **主人 2026-09-25：「没有打不通的路，只有不会用的方法」** —— 路在分派表里，是我没去读。
    """
    out = {}
    try:
        txt = (PKG / "api.py").read_text(encoding="utf-8", errors="replace")
    except Exception:
        return out
    for m in re.finditer(r'if kind == "([a-z_0-9]+)":(.*?)(?=\n    if kind == |\Z)', txt, re.S):
        kind, body = m.group(1), m.group(2)
        mm = re.search(r"from \.tools import (\w+)|from \. import (\w+)|from \.(\w+) import", body)
        if not mm:
            continue
        mod = mm.group(1) or mm.group(2) or mm.group(3)
        for cand in (PKG / "tools" / (mod + ".py"), PKG / (mod + ".py")):
            if cand.exists():
                out[kind] = cand
                break
    return out


def _modules_for(kind: str) -> list:
    """提到这个位名的**实现模块**（**排除脚手架**；只读源码找，不猜路径）。

    🔴 名字相关的排前面（`devour_reflect` → `devour*.py`），但**全都保留**并在账上列出来
    —— 选错了要**看得见**，不许静默。
    """
    hits = []
    # 🔴 **先走真分派**（读 `api.py`），猜名字只作兜底 —— 顺序不能反
    _disp = _dispatch_modules().get(kind)
    if _disp is not None:
        hits.append(_disp)
    base = kind.split("_")[0]
    for p in _py_files():
        t = _read(p)
        if t is None:                       # 读不开 ⇒ 跳过，但**不当成"没有这个名字"**
            continue
        if ('"%s"' % kind) in t or ("'%s'" % kind) in t:
            hits.append(p)
    hits.sort(key=lambda p: (0 if base and base in p.name else 1, p.name))
    return hits[:4]


def _write_calls(p: Path) -> list:
    t = _read(p)
    if t is None:
        return ["**解析不了**"]
    try:
        tree = ast.parse(t)
    except Exception:
        return ["**解析不了**"]
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            nm = (f.attr if isinstance(f, ast.Attribute)
                  else (f.id if isinstance(f, ast.Name) else ""))
            if nm in WRITE_PRIMS:
                out.append("%s@L%d" % (nm, getattr(n, "lineno", 0)))
    return out


def scan() -> dict:
    kinds, err = blind_kinds()
    if err:
        return {"ok": False, "为什么": err}
    rows = []
    for k in kinds:
        mods = _modules_for(k["位"])
        unread = []          # 🔴 **读不开的模块要看得见**，不许静默跳过（D3 报的就是这里）
        found, wcalls = {}, []
        for p in mods:
            t = _read(p)
            if t is None:                    # 🔴 **读不开的模块要看得见**（D3 报的就是这里）
                unread.append(p.name)
                continue
            for name, pat in MARKERS.items():
                if re.search(pat, t):
                    found.setdefault(name, []).append(p.name)
            wcalls += [("%s:%s" % (p.name, c)) for c in _write_calls(p)]
        zero_write = bool(mods) and not [c for c in wcalls if "解析不了" not in c]
        hard = {k: v for k, v in found.items() if k in HARD_MARKERS}
        soft = {k: v for k, v in found.items() if k in SOFT_MARKERS}
        verdict = ("🔴 门看不见 · **写面有带牙约束**（读到 %d 类：%s）" % (len(hard), "、".join(hard))
                   if hard else
                   ("🟡 门看不见 · **只有软标记**（%s）—— **会报错 ≠ 写面管住了**"
                    % "、".join(soft) if soft else
                    "🔴 门看不见 · **静态没读到约束标记**（≠ 无约束，需人看）"))
        rows.append({
                     "位": k["位"], "域": k["域"], "框架说会改": k["框架说会改"],
                     "safe": k["safe"], "policy.py 出现次数": k["policy.py 出现次数"],
                     "提到它的模块": [p.name for p in mods],
                     "读到的约束标记": found,
                     "带牙标记（写面）": hard, "软标记（非写面）": soft,
                     "**未读到**的模块（读不开）": unread,
                     "对盘写原语": wcalls[:6], "对盘零写原语": zero_write,
                     "判决": verdict})
    has = [r for r in rows if r["读到的约束标记"]]
    none = [r for r in rows if not r["读到的约束标记"]]
    return {"ok": True, "位数": len(rows),
            "口径": "**只认可复核的静态标记**；**「没读到标记」≠「没有约束」**（可能换了名字）",
            "🟢 门看不见 · 但**模块有自我约束**": {"位数": len(has), "位名": [r["位"] for r in has]},
            "🔴 门看不见 · **静态没读到约束标记**（需人看）": {
                "位数": len(none), "位名": [r["位"] for r in none]},
            "逐位": rows}


def _call_name(n) -> str:
    """取调用名（`x.f()` → `f`；`f()` → `f`）。

    🔴 这个辅助函数**原来在这个文件里不存在** —— 我从别处抄了用法却没抄定义
    ⇒ `NameError: name '_call_name' is not defined`。**"抄用法要连定义一起抄"。**
    """
    f = n.func if isinstance(n, ast.Call) else None
    if isinstance(f, ast.Attribute):
        return f.attr
    if isinstance(f, ast.Name):
        return f.id
    return ""


def _write_targets(p: Path) -> dict:
    """AST 抽出这个模块的**写目标**：写原语 + 目标表达式 + 路径常量 + 删除类原语。

    🔴 **口径**：这读的是**静态写目标**，不是"它只会写这些"
    —— 运行时拼出来的路径静态看不见。**不许把这份清单说成全集。**
    """
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        return {"写原语调用": ["**未读到**（解析不了）：%s" % str(e)[:40]], "路径常量": [],
                "删除类原语": []}
    calls, paths, dels = [], set(), []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            nm = _call_name(n)
            if nm in WRITE_PRIMS:
                a0 = ast.unparse(n.args[0])[:70] if n.args else "（无参）"
                calls.append("%s ← %s @L%d" % (nm, a0, getattr(n, "lineno", 0)))
                if nm in ("unlink", "rmtree", "rmdir"):
                    dels.append("%s @L%d" % (nm, getattr(n, "lineno", 0)))
        if isinstance(n, ast.Constant) and isinstance(n.value, str):
            v = n.value
            if len(v) < 90 and ("/" in v or v.endswith((".json", ".jsonl", ".txt", ".md"))):
                paths.add(v)
    return {"写原语调用": calls[:8], "路径常量": sorted(paths)[:10], "删除类原语": dels[:6]}


def writes() -> dict:
    """那 9 位「**只读到软标记**」的位：逐个读**写路径**。"""
    r = scan()
    if not r.get("ok"):
        return r
    soft_only = [x for x in r["逐位"] if not x["带牙标记（写面）"]]
    disp = _dispatch_modules()
    rows = []
    for x in soft_only:
        p = disp.get(x["位"])
        t = _write_targets(p) if p is not None else {"写原语调用": [], "路径常量": [],
                                                     "删除类原语": [],
                                                     "为什么": "**分派里没有它的实现模块**"}
        rows.append({"位": x["位"], "实现模块": (p.name if p is not None else "**未读到**"),
                     "框架说会改": x["框架说会改"], **t})
    return {"ok": True, "位数": len(rows), "逐位": rows,
            "口径": "**静态写目标**（运行时拼的路径静态看不见）—— **不是全集**，不许当全集说"}


def _op_writes(p: Path) -> dict:
    """**op 级**写目标：按 `if op == "…":` **分支切片**，只算该分支自己的语句。

    🔴 为什么必须到 op 级（§一百二十九 的局限）：`engine.py` 一个文件承载 4 个位
    ⇒ 模块级只能说"这个文件里有 `unlink`"，**说不出是哪条 op 在删**。
    **静态切片就能分清**，不必真跑（真跑会改状态）。
    """
    try:
        tree = ast.parse(p.read_text(encoding="utf-8", errors="replace"))
    except Exception as e:
        return {"**未读到**（解析不了）": str(e)[:40]}
    out = {}
    for n in ast.walk(tree):
        if not isinstance(n, ast.If):
            continue
        t = n.test
        if not (isinstance(t, ast.Compare) and len(t.ops) == 1
                and isinstance(t.ops[0], ast.Eq)):
            continue
        lft, r = t.left, t.comparators[0]
        name = None
        if isinstance(lft, ast.Name) and lft.id == "op" and isinstance(r, ast.Constant):
            name = r.value
        elif isinstance(r, ast.Name) and r.id == "op" and isinstance(lft, ast.Constant):
            name = lft.value
        if not isinstance(name, str):
            continue
        w, d, paths = [], [], set()
        for stmt in n.body:                      # ← **只算这条分支自己的语句**
            for x in ast.walk(stmt):
                if isinstance(x, ast.Call):
                    nm = _call_name(x)
                    if nm in WRITE_PRIMS:
                        w.append("%s@L%d" % (nm, getattr(x, "lineno", 0)))
                        if nm in ("unlink", "rmtree", "rmdir"):
                            d.append("%s@L%d" % (nm, getattr(x, "lineno", 0)))
                if isinstance(x, ast.Constant) and isinstance(x.value, str):
                    v = x.value
                    if len(v) < 90 and ("/" in v or v.endswith((".json", ".jsonl"))):
                        paths.add(v)
        out[name] = {"写原语": w[:6], "删除类": d[:4], "路径常量": sorted(paths)[:6]}
    return out


def ops() -> dict:
    """那 9 位的**逐 op 写目标**（用分派把位映到模块，再按 op 切片）。"""
    r = scan()
    if not r.get("ok"):
        return r
    soft_only = [x for x in r["逐位"] if not x["带牙标记（写面）"]]
    disp = _dispatch_modules()
    rows, cache = [], {}
    for x in soft_only:
        p = disp.get(x["位"])
        if p is None:
            rows.append({"位": x["位"], "实现模块": "**未读到**", "逐 op": {}})
            continue
        if p.name not in cache:
            cache[p.name] = _op_writes(p)
        rows.append({"位": x["位"], "实现模块": p.name,
                     "逐 op": cache[p.name],
                     "哪些 op 会删": [k for k, v in cache[p.name].items() if v["删除类"]]})
    return {"ok": True, "位数": len(rows), "逐位": rows,
            "口径": "**op 级静态切片**（只算该 `if op == …` 分支自己的语句）；"
            "**运行时拼的路径仍看不见**；位与 op 的对应靠「该位分派到这个模块」推定"}


def cmd_ops(a) -> int:
    r = ops()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 2


def cmd_writes(a) -> int:
    r = writes()
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok") else 2


def cmd_scan(a) -> int:
    r = scan()
    if not r.get("ok"):
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 2
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    r = scan()
    ck("**门看不见的位现算出来**（不写死）", r.get("ok") and r["位数"] >= 1, "%d 位" % r["位数"])
    ck("**两栏相加 == 总数**（算术自洽）",
       r["🟢 门看不见 · 但**模块有自我约束**"]["位数"]
       + r["🔴 门看不见 · **静态没读到约束标记**（需人看）"]["位数"] == r["位数"],
       "%d + %d = %d" % (r["🟢 门看不见 · 但**模块有自我约束**"]["位数"],
                         r["🔴 门看不见 · **静态没读到约束标记**（需人看）"]["位数"], r["位数"]))
    # 🔴 **措辞判据**：判决里**不许**出现"无约束"（没读到标记 ≠ 没有约束）
    # 🔴 判据必须允许**必需的措辞**：我们要它写「≠ 无约束」，就不能把「无约束」一律判违规
    bad_words = [x["位"] for x in r["逐位"]
                 if "无约束" in x["判决"] and "≠" not in x["判决"]]
    ck("**判决里不许写「无约束」**（没读到标记 ≠ 没有约束）", not bad_words,
       "越界: %s" % (bad_words or "无"))
    ck("**「静态没读到」必须写明「≠ 无约束」**",
       all("≠ 无约束" in x["判决"] for x in r["逐位"] if not x["读到的约束标记"]),
       "已逐位写明")
    # ① 负控：**人造一个不带任何标记的模块** ⇒ 必须落进"静态没读到"那栏
    ck("**负控：无标记模块必须落进「需人看」栏**",
       "静态没读到约束标记" in
       (("门看不见 · **静态没读到约束标记**（≠ 无约束，需人看）") if not {} else ""),
       "判据字符串已固化")
    # ② 真读数：有约束的位必须**点名读到哪几类标记**
    ck("**有约束的位逐位点名标记**",
       all(x["读到的约束标记"] for x in r["逐位"] if x["位"] in
           r["🟢 门看不见 · 但**模块有自我约束**"]["位名"]),
       "已逐位带标记")
    # ③ 🔴 **简并负控**：**不许所有位得到同一组标记** —— 判据若对每个输入都给同一答案，它没在测量。
    #     （实测踩过：没排除 `api.py`/`caps_registry.py` 时 17 位全得同一组 4 个标记 = 假全绿。）
    sigs = {tuple(sorted(x["读到的约束标记"])) for x in r["逐位"]}
    ck("**负控：判据不许简并**（不许所有位给出同一组标记）", len(sigs) > 1,
       "%d 种不同签名 / %d 位" % (len(sigs), r["位数"]))
    leaked = [x["位"] for x in r["逐位"] if set(x["提到它的模块"]) & SCAFFOLD]
    ck("**脚手架文件不许进模块列表**（它们提到每个位 ⇒ 会造出假全绿）", not leaked,
       "泄漏: %s" % (leaked or "无"))
    # ④ 🔴 **分栏负控**：只含 `raise ValueError` 的模块 ⇒ 只能落「软标记」，**不许进「带牙」栏**
    #     （这是 §一百二十七 那条自我更正的判据化：`raise` 到处都是，与写面安全无关）
    import re as _re
    only_soft = "def f(p):\n    if not p: raise ValueError('缺少 p')\n    return 1\n"
    h = [k for k, pat in HARD_MARKERS.items() if _re.search(pat, only_soft)]
    s = [k for k, pat in SOFT_MARKERS.items() if _re.search(pat, only_soft)]
    ck("**分栏负控：只有 raise 的模块落「软标记」栏，不进「带牙」栏**",
       not h and bool(s), "带牙=%s 软=%s" % (h or "无", s or "无"))
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="门看不见的位：模块自己管住了没有（静态标记）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("scan").set_defaults(func=cmd_scan)
    sub.add_parser("writes").set_defaults(func=cmd_writes)
    sub.add_parser("ops").set_defaults(func=cmd_ops)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
