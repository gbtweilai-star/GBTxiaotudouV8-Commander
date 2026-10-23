#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""能力位「门 × 写口」分档（N8 的静态尺子）—— 覆盖**全部在册位**，不执行任何能力位。

⚠️ 与既有工具的边界（写清楚，免得重复造轮子）：
  · `caps-census.py`       = **静态**查注册表/policy/preflight（不执行）
  · `caps-runtime-census.py` = **运行时**把"自判可自动跑"的位真空参**真跑**一次
                              （它的回执 `output/blueprint-audit/caps-runtime-census.json`，
                               现读是 **2026-09-25** 的、98 位 —— 已过期，刷新要 45 分钟预算）
  · **本件** = 在两者之间补一层：把**全部 341 位**按「空载荷门作用域 × handler 写盘原语」分四档，
              专门回答 N8 那句话：**谁需要授权、谁零作用域但其实会写盘**。只看代码，不跑位。

四档（互斥）：
  · `需授权`        = `policy.evaluate(kind, {})` 的 scopes 非空
  · `零作用域·模块有写口` = scopes 空 且 handler **模块** AST 里有写盘原语
    🔴 2026-10-22 自纠（第 10 次，留痕）：这档原来是**模块级**粗判，我却叫它"真风险档"——
       实测反例：`alerts` 被列进来，但它的 `alerts()` 只调 `check_audit()` 就返回，
       真正写盘的是**同模块的另一个函数** `_autofix()`（只在 `scan(autofix=True)` 里调用）。
       ⇒ 现口径：这一档只说明"**该位所在模块**有写盘原语"，**不判该位可达**；
          要判可达得做调用链分析（另立 TODO，不在本件里假装做到）。
  · `零作用域·只读`   = scopes 空 且无写盘原语
  · `无 handler`     = handler 指不到模块（幽灵位）

用法：py -3.14 tools/codex-scripts/caps-write-gate-census.py [--json]
"""
import argparse
import ast
import json
import os
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "state", "caps_write_gate_census.json")
OUT_MD = os.path.join(ROOT, "outputs", "caps-census", "门与写口分档.md")

WRITE_NAMES = {"write_text", "write_bytes", "rmtree", "move", "remove", "rename", "unlink",
               "makedirs", "truncate", "dumps_to_file"}


def kind_modules():
    """从 `api.py` 的分派分支里抽 `kind -> [模块名]`（AST 级，不猜）。

    🔴 2026-10-22 自纠（第一次跑就抓到，留痕）：我原先把注册表的 `handler` 当成**模块路径**，
       实测它是**裸名**（`'codex_status'` / `'brain_vault'`，341/341 都有）⇒ 于是 278 位被判成
       "无 handler"，**那是我的量法错，不是盘上没有实现**。现在改成从真正的分派面取模块：
       `if kind == "X":` 分支体里的 `from . import M` / `from .M import ...`。
    """
    import re
    src = open(os.path.join(ROOT, "gbt_allinone", "api.py"), encoding="utf-8").read()
    blocks = re.split(r'(?m)^    if kind == "([A-Za-z0-9_]+)":\s*$', src)
    out = {}
    # blocks = [head, kind1, body1, kind2, body2, ...]
    for i in range(1, len(blocks) - 1, 2):
        kind, body = blocks[i], blocks[i + 1]
        body = re.split(r'(?m)^    if kind == "', body)[0]
        mods = set(re.findall(r'from \. import ([A-Za-z0-9_, ]+)', body))
        mods |= set(re.findall(r'from \.([A-Za-z0-9_]+) import', body))
        names = []
        for chunk in mods:
            for m in str(chunk).split(","):
                m = m.strip()
                if m:
                    names.append(m)
        if names:
            out[kind] = sorted(set(names))
    return out


def source_of(handler, kmods=None):
    """返回 (找到的第一个模块文件, 源码)。handler 是裸名时用分派面找模块。"""
    cands = []
    h = str(handler or "")
    if ":" in h:
        cands.append(h.split(":")[0])
    if h and not h.startswith("gbt_allinone"):
        cands.append(h)
    for m in (kmods or {}).get(h, []):
        cands.append(m)
    for mod in cands:
        mm = mod if mod.startswith("gbt_allinone") else "gbt_allinone." + mod
        p = os.path.join(ROOT, *mm.split(".")) + ".py"
        if not os.path.isfile(p):
            p2 = os.path.join(ROOT, *mm.split("."), "__init__.py")
            if os.path.isfile(p2):
                p = p2
            else:
                continue
        try:
            return p, open(p, encoding="utf-8", errors="replace").read()
        except OSError:
            return p, None
    return None, None


def write_primitives(src):
    hits = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return hits
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = getattr(f, "id", None) or getattr(f, "attr", None)
        if name in WRITE_NAMES:
            hits.append(name)
        elif name == "open" and len(node.args) >= 2:
            for a in node.args[1:]:
                if isinstance(a, ast.Constant) and isinstance(a.value, str) \
                        and any(ch in a.value for ch in "wax+"):
                    hits.append("open(%s)" % a.value)
    return sorted(set(hits))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    sys.path.insert(0, ROOT)
    from gbt_allinone import caps_registry as CR
    from gbt_allinone.security import policy as POL

    t0 = time.time()
    kmods = kind_modules()          # kind → [模块名]（从 api.py 分派面 AST 抽）
    rows = []
    for name, meta in sorted((CR.BENIGN_CAPS or {}).items()):
        meta = meta or {}
        try:
            d = POL.evaluate(name, {})
            scopes = list(getattr(d, "scopes", ()) or ())
            risk = getattr(d, "risk", None)
        except Exception as e:  # noqa: BLE001
            scopes, risk = ["<evaluate失败:%s>" % type(e).__name__], None
        p, src = source_of(meta.get("handler"), kmods)
        w = write_primitives(src) if src else []
        if not p:
            bucket = "分派无 import（实现待查）"
        elif scopes:
            bucket = "需授权"
        elif w:
            bucket = "零作用域·模块有写口"
        else:
            bucket = "零作用域·只读"
        rows.append({"cap": name, "domain": meta.get("domain"), "handler": meta.get("handler"),
                     "handler_file": os.path.relpath(p, ROOT) if p else None,
                     "scopes": scopes, "risk": risk, "writes": w[:6], "bucket": bucket})

    by = {}
    for r in rows:
        by[r["bucket"]] = by.get(r["bucket"], 0) + 1
    risky = [r for r in rows if r["bucket"] == "零作用域·模块有写口"]
    ghost = [r for r in rows if r["bucket"] == "分派无 import（实现待查）"]
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "registry": len(rows), "by_bucket": by,
           "zero_scope_with_writes": [r["cap"] for r in risky],
           "ghost": [r["cap"] for r in ghost], "rows": rows,
           "elapsed_s": round(time.time() - t0, 1),
           "boundary": "本件静态；运行时真调见 caps-runtime-census.py（其回执 2026-09-25，98 位，已过期）",
           "note": "门以 policy.evaluate 空载荷为准 —— 空载荷零作用域 ≠ 只读（op 依赖位会换一套）"}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, OUT)

    if a.json:
        print(json.dumps({k: v for k, v in out.items() if k != "rows"}, ensure_ascii=False, indent=2))
        return 0

    os.makedirs(os.path.dirname(OUT_MD), exist_ok=True)
    lines = ["# 能力位「门 × 写口」分档（N8）", "",
             "> 生成：`py -3.14 tools/codex-scripts/caps-write-gate-census.py` · %s" % out["at"],
             "> 全部 **%d** 位在册位 · 只看代码不跑位（运行时真调是另一个工具，其回执已过期）" % len(rows),
             "> 口径：门=`policy.evaluate(kind, {})`；写口=handler 模块 AST；**零作用域 ≠ 只读**",
             "", "| 档 | 位数 |", "|---|---|"]
    for b, n in sorted(by.items(), key=lambda kv: -kv[1]):
        lines.append("| %s | **%d** |" % (b, n))
    lines += ["", "## 🔴 零作用域·所在模块有写盘原语（%d 位，**模块级，未判可达**）" % len(risky), ""]
    if risky:
        lines += ["| 能力位 | 域 | handler 文件 | 写原语 |", "|---|---|---|---|"]
        for r in risky:
            lines.append("| `%s` | %s | %s | %s |"
                         % (r["cap"], r["domain"], r["handler_file"], "、".join(r["writes"])))
    else:
        lines.append("（无）")
    if ghost:
        lines += ["", "## 分派分支里没 import 的位（%d 位，**待查，不等于没有实现**）" % len(ghost), "",
                  "、".join("`%s`" % r["cap"] for r in ghost)]
    lines += ["", "## 需授权位（%d 位）" % by.get("需授权", 0), "",
              "| 能力位 | scopes（空载荷） | risk | 域 |", "|---|---|---|---|"]
    for r in rows:
        if r["bucket"] == "需授权":
            lines.append("| `%s` | %s | %s | %s |"
                         % (r["cap"], "、".join(r["scopes"]), r["risk"], r["domain"]))
    tmp_md = OUT_MD + ".tmp"
    with open(tmp_md, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines) + "\n")
    os.replace(tmp_md, OUT_MD)

    print("门×写口分档：%d 位（%.1f 秒）" % (len(rows), out["elapsed_s"]))
    for b, n in sorted(by.items(), key=lambda kv: -kv[1]):
        print("  %-18s %3d" % (b, n))
    print("  零作用域但会写盘 %d 位%s" % (len(risky),
                                     ("：" + "、".join(r["cap"] for r in risky[:12])) if risky else ""))
    print("  人读：%s" % OUT_MD)
    return 0


if __name__ == "__main__":
    sys.exit(main())
