#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""「能力有没有被误限制」排查（只读，逐位 × 逐 op 现算门）。

口径（写死）：
  ① 从**源码**枚举每个能力位可能的 op：扫描其 handler 模块里 `op == "X"`、`op in ("a","b")`、
     `action == "X"` 三种写法 —— 不手写清单（手写清单会带幽灵名，P30）。
  ② 对每个 (kind, op) 调 `security/policy.py` 的 `evaluate()`，拿**该 op 真正要的作用域**。
  ③ 按 op 名分两类：
       读类动词 = list status get query read info show search inspect count stats preview plan
                  ask ls cat peek audit health whoami
       写类动词 = send write apply delete publish run execute commit create update remove purge
                  install deploy register mark set fix tick submit release
  ④ 判两种异常：
       **A. 疑似误限制** = 读类动词，但门要了非空作用域（这就是 voice_orchestra.query 那一类）；
       **B. 疑似漏门**   = 写类动词，但门要的作用域为空（零作用域却会改状态）。
输出：`state/caps-restriction-audit.json` + `outputs/caps-census/误限制排查.md`
"""
import json
import os
import re
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "state", "caps-restriction-audit.json")
OUT_MD = os.path.join(ROOT, "outputs", "caps-census", "误限制排查.md")
PKG = os.path.join(ROOT, "gbt_allinone")

READ_VERBS = {"list", "status", "get", "query", "read", "info", "show", "search", "inspect",
              "count", "stats", "preview", "plan", "ask", "ls", "cat", "peek", "audit",
              "health", "whoami", "describe", "explain"}
WRITE_VERBS = {"send", "write", "apply", "delete", "publish", "run", "execute", "commit",
               "create", "update", "remove", "purge", "install", "deploy", "register", "mark",
               "set", "fix", "tick", "submit", "release", "reset", "rotate", "grant", "revoke"}

OP_PATTERNS = [
    re.compile(r'op\s*==\s*"([a-z_][a-z0-9_]*)"'),
    re.compile(r'action\s*==\s*"([a-z_][a-z0-9_]*)"'),
]
OP_IN_PATTERN = re.compile(r'(?:op|action)\s+(?:not\s+)?in\s*\(([^)]+)\)')


def ops_in_source(src):
    ops = set()
    for p in OP_PATTERNS:
        ops |= set(p.findall(src))
    for grp in OP_IN_PATTERN.findall(src):
        for m in re.findall(r'"([a-z_][a-z0-9_]*)"', grp):
            ops.add(m)
    return ops


def module_of(api_src, kind):
    m = re.search(r'(?m)^    if kind == "%s":\s*$' % re.escape(kind), api_src)
    if not m:
        return None
    body = api_src[m.end():]
    nxt = re.search(r'(?m)^    if kind == "', body)
    body = body[:nxt.start()] if nxt else body
    mods = re.findall(r'from \. import ([A-Za-z0-9_, ]+)', body)
    mods += re.findall(r'from \.([A-Za-z0-9_]+) import', body)
    names = []
    for chunk in mods:
        for x in str(chunk).split(","):
            x = x.strip()
            if x:
                names.append(x)
    return names[0] if names else None


def main():
    from gbt_allinone import caps_registry as CR
    from gbt_allinone.security import policy as POL

    api_src = open(os.path.join(PKG, "api.py"), encoding="utf-8").read()
    rows = []
    for kind in sorted((CR.BENIGN_CAPS or {})):
        mod = module_of(api_src, kind)
        src = ""
        if mod:
            p = os.path.join(PKG, mod + ".py")
            if not os.path.isfile(p):
                p2 = os.path.join(PKG, mod, "__init__.py")
                p = p2 if os.path.isfile(p2) else p
            if os.path.isfile(p):
                src = open(p, encoding="utf-8", errors="replace").read()
        ops = ops_in_source(src) if src else set()
        entry = {"cap": kind, "module": mod, "ops": {}, "misrestricted": [], "ungated": []}
        for op in sorted(ops):
            try:
                d = POL.evaluate(kind, {"op": op})
                sc = list(getattr(d, "scopes", ()) or [])
            except Exception as e:  # noqa: BLE001
                sc = ["<evaluate失败:%s>" % type(e).__name__]
            entry["ops"][op] = sc
            if op in READ_VERBS and sc:
                entry["misrestricted"].append({"op": op, "scopes": sc})
            if op in WRITE_VERBS and not sc:
                entry["ungated"].append({"op": op})
        if entry["misrestricted"] or entry["ungated"] or entry["ops"]:
            rows.append(entry)

    mis = [(r["cap"], x) for r in rows for x in r["misrestricted"]]
    ung = [(r["cap"], x) for r in rows for x in r["ungated"]]
    receipt = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
               "caps_scanned": len(CR.BENIGN_CAPS or {}),
               "caps_with_ops": len(rows),
               "ops_total": sum(len(r["ops"]) for r in rows),
               "misrestricted": len(mis), "ungated": len(ung),
               "rows": rows}
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(receipt, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, OUT)

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    lines = ["# 能力「有没有被误限制」排查（只读）", "",
             "> 生成：`py -3.14 tools/codex-scripts/caps-restriction-audit.py` · %s" % receipt["at"],
             "> 口径：op 从**源码**枚举；门用 `policy.evaluate(kind,{op})` 现算；"
             "读类动词要了作用域 = 疑似误限制；写类动词零作用域 = 疑似漏门。",
             "", "## 汇总", "",
             "| 项 | 读数 |", "|---|---|",
             "| 扫过的能力位 | **%d** |" % receipt["caps_scanned"],
             "| 有可枚举 op 的位 | %d |" % receipt["caps_with_ops"],
             "| 枚举到的 (位,op) 组合 | %d |" % receipt["ops_total"],
             "| **疑似误限制**（读类要作用域） | **%d** |" % receipt["misrestricted"],
             "| 疑似漏门（写类零作用域） | %d |" % receipt["ungated"],
             "", "## A. 疑似误限制（读类动作被要求授权）", "",
             "| 能力位 | op | 门要的作用域 |", "|---|---|---|"]
    if mis:
        for cap, x in mis:
            lines.append("| `%s` | `%s` | %s |" % (cap, x["op"], "、".join(x["scopes"])))
    else:
        lines.append("| — | — | （无） |")
    lines += ["", "## B. 疑似漏门（写类动作零作用域）", "",
              "| 能力位 | op |", "|---|---|"]
    if ung:
        for cap, x in ung:
            lines.append("| `%s` | `%s` |" % (cap, x["op"]))
    else:
        lines.append("| — | （无） |")
    lines += ["", "（完整逐位读数见 `state/caps-restriction-audit.json`）"]
    tmp = OUT_MD + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp, OUT_MD)

    print("误限制排查：位 %d · (位,op) 组合 %d" % (receipt["caps_scanned"], receipt["ops_total"]))
    print("  A 疑似误限制 %d 条" % receipt["misrestricted"])
    for cap, x in mis[:15]:
        print("    %-20s op=%-12s 要 %s" % (cap, x["op"], "、".join(x["scopes"])))
    print("  B 疑似漏门 %d 条" % receipt["ungated"])
    for cap, x in ung[:10]:
        print("    %-20s op=%s（零作用域）" % (cap, x["op"]))
    print("  人读：%s" % OUT_MD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
