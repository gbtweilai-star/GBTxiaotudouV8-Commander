# -*- coding: utf-8 -*-
"""omni-monitor —— 万能插自述/实现/声明 **三向对账**（AST 现读，不写死）。

⚠️ **补回不存在的判据。** 两处注释都写着「判据在 `tools/codex-scripts/omni-monitor.py --gap`
（AST 三向对账）」：
    · gbt_allinone/omni_plug.py:1668
    · gbt_allinone/caps_registry.py:1615
而 2026-11-05 实测：这个文件**不存在**，`gbt_allinone/omni_monitor.py` 也没有 `--gap`／`main()`／
argparse（它只是监控采样模块）。也就是说「判据在 X」这句话本身没有判据 ——
自述漏 5 个 op 那种事，就是在这种"以为有人看着"的状态下发生的。

三向：
  ① **实现**：`omni_plug._dispatch` 里 `op == "x"` / `op in (...)` 的字面量；
  ② **自述**：同函数 not-known 分支里的 `known` 列表；
  ③ **声明**：`caps_registry.BENIGN_CAPS["omni_plug"]["desc"]` 里 `op=xxx` 提到的 op
     （支持 `op=a/b/c` 斜杠列举）。

任一方向漏项都算 gap，退出码 1。

用法：
    python tools/codex-scripts/omni-monitor.py --gap      # 三向对账（有 gap 则 exit 1）
    python tools/codex-scripts/omni-monitor.py            # 打印三向读数
"""
from __future__ import annotations

import argparse
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

PLUG = os.path.join(ROOT, "gbt_allinone", "omni_plug.py")
CAP = "omni_plug"

OP_RE = re.compile(r"op\s*[=:]\s*([a-z0-9_]+(?:\s*/\s*[a-z0-9_]+)*)", re.I)

# 否定提及（2026-11-06 补）：desc 里写「**没有 `op=all`**」是在**声明不存在**，
# 不是声明存在。原实现把它算进「声明」，于是自述/实现都干净的位也会报 gap（实测假阳）。
NEG_RE = re.compile(r"(没有|并无|无|不是|并非|不含|不支持|不认|旧写法|已废|禁用|别用|去掉|不再|废弃)\s*[`\"'「【]?\s*$")


def _cstr(n):
    return n.value if isinstance(n, ast.Constant) and isinstance(n.value, str) else None


def _find(tree, name):
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    return None


def _op_literals(fn):
    got = set()
    for n in ast.walk(fn):
        if not isinstance(n, ast.Compare) or len(n.ops) != 1:
            continue
        left, op, right = n.left, n.ops[0], n.comparators[0]
        if isinstance(left, ast.Name) and left.id == "op":
            tgt = right
        elif isinstance(right, ast.Name) and right.id == "op":
            tgt = left
        else:
            continue
        if isinstance(op, ast.Eq):
            s = _cstr(tgt)
            if s:
                got.add(s)
        elif isinstance(op, ast.In) and isinstance(tgt, (ast.Tuple, ast.List, ast.Set)):
            for e in tgt.elts:
                s = _cstr(e)
                if s:
                    got.add(s)
    return got


def three_way() -> dict:
    src = open(PLUG, encoding="utf-8").read()
    tree = ast.parse(src, filename=PLUG)
    fn = _find(tree, "_dispatch")
    if fn is None:
        return {"ok": False, "error": "找不到 omni_plug._dispatch"}

    impl = _op_literals(fn)

    declared = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if _cstr(k) == "known" and isinstance(v, ast.List):
                    for e in v.elts:
                        s = _cstr(e)
                        if s:
                            declared.add(s)

    from gbt_allinone.caps_registry import BENIGN_CAPS

    meta = BENIGN_CAPS.get(CAP) or {}
    desc = str(meta.get("desc") or "")
    in_desc, negated = set(), set()
    for m in OP_RE.finditer(desc):
        head = desc[max(0, m.start() - 16):m.start()]
        target = negated if NEG_RE.search(head) else in_desc
        for part in m.group(1).split("/"):
            p = part.strip().lower()
            if p:
                target.add(p)

    return {
        "ok": True,
        "impl": impl,
        "declared": declared,
        "in_desc": in_desc,
        "desc_negated": sorted(negated),
        "impl_minus_declared": sorted(impl - declared),
        "declared_minus_impl": sorted(declared - impl),
        "desc_minus_impl": sorted(in_desc - impl),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="万能插三向对账（实现 / 自述 / 声明）")
    ap.add_argument("--gap", action="store_true", help="有差集就 exit 1")
    args = ap.parse_args(argv)

    r = three_way()
    if not r.get("ok"):
        print("对账失败：%s" % r.get("error"))
        return 2

    impl, dec, desc = r["impl"], r["declared"], r["in_desc"]
    print("① 实现（_dispatch 分支）: %d" % len(impl))
    print("② 自述（known 列表）    : %d" % len(dec))
    print("③ 声明（desc 里 op=…）  : %d" % len(desc))
    print()

    g1 = r["impl_minus_declared"]
    g2 = r["declared_minus_impl"]
    g3 = r["desc_minus_impl"]

    print("实现 − 自述（自述漏项，照自述调用会摸不到）:", g1 or "无")
    print("自述 − 实现（自述写了但没实现）        :", g2 or "无")
    print("声明 − 实现（desc 说了但没实现）        :", g3 or "无")

    gaps = bool(g1 or g2 or g3)
    if not args.gap:
        print()
        print("加 --gap：有差集就 exit 1（供 CI / 判据调用）")
        return 0
    print()
    print("结论:", "有 gap" if gaps else "三向一致")
    return 1 if gaps else 0


if __name__ == "__main__":
    raise SystemExit(main())
