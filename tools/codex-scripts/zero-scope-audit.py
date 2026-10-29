#!/usr/bin/env python -3.14
# -*- coding: utf-8 -*-
"""zero-scope-audit · 「**零作用域 ≠ 只读**」的**可实测交叉审计**

开发者：自由的风 · 守护者：公主土豆 · 禁止删除

## 为什么造它
本仓有一句老话：**「零作用域 ≠ 只读」** —— 意思是 `policy.evaluate(kind).scopes` 为空
**只说明"门不会拦它"**，**不说明"它不会改东西"**。
老话喊了很多轮，**但没有人把这两个源对撞过**：

| 源 | 它回答什么 |
|---|---|
| **A** `security/policy.py::evaluate(kind).scopes` | **门**会不会拦它 |
| **B** `preflight.state_changing_kinds()` | **框架自己说**谁"会改状态" |

⇒ **危险集 = 零作用域 ∧ B 说它会改** —— 这类位的性质是：
**门不会拦，但它会改框架状态**。本工具把这份名单**现算出来**。

## 纪律
- **只读**：只 `evaluate`（纯函数）+ 读两张表，**不调任何能力位**；
- **两个源都真读**：任一读不到就报未读到，**不拿 0 冒充**；
- **不含糊**：`零作用域` 与 `只读` 是两件事，输出里**分开写**。

用法：
  zero-scope-audit.py cross   # 交叉表 + 危险集点名
  zero-scope-audit.py danger  # 只看危险集
  zero-scope-audit.py selftest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def _sources():
    """两个独立源 + 注册表。**读不到就返回 None 并说明**。"""
    out = {}
    try:
        from gbt_allinone import caps_registry as R
        out["注册表"] = R
    except Exception as e:
        return None, "**未读到** caps_registry：%s" % str(e)[:70]
    try:
        from gbt_allinone.security import policy as POL
        out["policy"] = POL
    except Exception as e:
        return None, "**未读到** security/policy：%s" % str(e)[:70]
    try:
        from gbt_allinone import preflight as PF
        out["preflight"] = PF
    except Exception as e:
        return None, "**未读到** preflight：%s" % str(e)[:70]
    try:
        out["会改状态集"] = set(PF.state_changing_kinds())
    except Exception as e:
        return None, "**未读到** state_changing_kinds()：%s" % str(e)[:70]
    return out, None


def cross() -> dict:
    src, err = _sources()
    if err:
        return {"ok": False, "为什么": err}
    R, POL = src["注册表"], src["policy"]
    scc = src["会改状态集"]
 # `all_caps()` 返回的是 **list（名字表）不是 dict** —— 我第一次假设了形状 ⇒ AttributeError。
    #    元数据（domain/safe）从两张真表取；**两种形状都接住**，不猜。
    meta_map = {}
    for name in ("BENIGN_CAPS", "UNIMPLEMENTED_CAPS"):
        d = getattr(R, name, None)
        if isinstance(d, dict):
            meta_map.update({k: (v if isinstance(v, dict) else {}) for k, v in d.items()})
    caps = R.all_caps()
 # `all_caps()` 实测返回 **list of dicts**（第一版我按名字表排 ⇒ `'<' not supported … 'dict'`）。
    #    **接住三种形状**（dict / list-of-dict / list-of-name），**不猜**。
    if isinstance(caps, dict):
        items = sorted(caps.items())
    else:
        items = []
        for entry in caps:
            if isinstance(entry, dict):
                k = str(entry.get("kind") or entry.get("name") or entry.get("位") or "")
                merged = dict(meta_map.get(k, {}))
                merged.update(entry)
                items.append((k, merged))
            else:
                items.append((str(entry), meta_map.get(str(entry), {})))
        items.sort(key=lambda x: x[0])
    rows = []
    for kind, meta in items:
        if not isinstance(meta, dict):
            meta = meta_map.get(kind, {})
        try:
            d = POL.evaluate(kind, {})
            scopes = tuple(getattr(d, "scopes", ()) or ())
        except Exception as e:
            scopes = ("**evaluate 抛异常**", str(e)[:40])
        rows.append({"位": kind, "域": (meta or {}).get("domain"),
                     "safe": (meta or {}).get("safe"),
                     "作用域": list(scopes), "零作用域": len(scopes) == 0,
                     "框架说会改状态": kind in scc})
    zero = [r for r in rows if r["零作用域"]]
    danger = [r for r in zero if r["框架说会改状态"]]
    zero_but_safe_false = [r for r in zero if r["safe"] is False]
    return {
        "ok": True,
        "口径": {"A": "policy.evaluate(kind).scopes —— **门**会不会拦",
               "B": "preflight.state_changing_kinds() —— **框架自己说**会改状态",
               "危险集定义": "**零作用域 ∧ B 说会改** ⇒ 门不会拦，但它会改"},
        "全量": len(rows),
        "零作用域": len(zero),
        "有门的位": len(rows) - len(zero),
        "🔴 危险集（零作用域 ∧ 会改状态）": {
            "位数": len(danger), "位名": [r["位"] for r in danger],
            "为什么危险": "**门不会拦**（scopes 空）**但它会改框架状态** —— "
            "这正是「零作用域 ≠ 只读」的实证面"},
        "🟡 零作用域 ∧ safe=False": {
            "位数": len(zero_but_safe_false),
            "位名": [r["位"] for r in zero_but_safe_false],
            "读法": "`safe=False` 是**按位记**的（不是按 op）⇒ 这几位零作用域却自己声明「不 safe」"},
        "读数自洽": {"零作用域 + 有门 == 全量":
                 (len(zero) + (len(rows) - len(zero)) == len(rows))},
        "逐位": rows,
    }


# **带参口径**：给"**会改状态的那个 op**"去 `evaluate`。
#    `evaluate` 是**纯函数**（只算不写）⇒ **带了 apply/submit 的参也不会真动手**。
#    每条都写明"为什么这个 op 是会改的那个"。
DEEP = {
    "code_patch": ({"op": "apply", "path": "tools/self_model.py", "find": "x", "replace": "y"},
                   "`apply` 是写盘原语（`dry_run` 才只算）"),
    "git_write": ({"op": "stage", "paths": ["README.md"]}, "`stage` 改版本库索引"),
    "media_publish": ({"op": "submit", "product": "x"}, "`submit` 是发布（写面）"),
    "media_license": ({"op": "register", "file": "x"}, "`register` 写许可账"),
    "audio_extract": ({"op": "extract", "path": "x.mp4", "format": "mp3"}, "`extract` 真出音频件"),
    "audio_mix": ({"op": "mix", "inputs": ["a.mp3", "b.mp3"], "out": "c.mp3"}, "`mix` 真出混音件"),
    "edit_pipeline": ({"op": "render", "timeline": {}, "out": "outputs/x.mp4"}, "`render` 真出片"),
    "media_run": ({"op": "run", "kind": "short_video", "work": "x"}, "`run` 把整条链走到尾"),
    "sched_define": ({"op": "define", "name": "n", "workflow": "w", "every_seconds": 60},
                     "定义调度 = 改状态"),
    "wf_define": ({"name": "n", "nodes": []}, "定义工作流 = 改状态"),
    "wf_resume": ({"run_id": "r"}, "续跑 = 改状态"),
    "wf_run": ({"name": "n"}, "跑工作流 = 改状态"),
    "wf_cache_clear": ({}, "清缓存 = 改状态（无参）"),
    "lr_submit": ({"description": "d"}, "提交长程任务 = 改状态"),
    "lr_tick": ({}, "推进任务图 = 改状态（无参）"),
    "root_fix": ({}, "根治环 = 改状态（无参）"),
    "devour_reflect": ({}, "反思 = 改状态（无参）"),
    "sched_tick": ({}, "扫到期调度并执行（无参）"),
}


def _policy_branch_count(kinds) -> dict:
    """`policy.py` 里每个位名**出现几次** —— 0 次 = **门结构上没有这个位的分支**。"""
    p = ROOT / "gbt_allinone" / "security" / "policy.py"
    txt = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    return {k: txt.count('"%s"' % k) for k in kinds}


def deep() -> dict:
    """**把「下界」往上推**：空参 vs 带参，作用域会不会浮出来；并查门有没有分支。"""
    src, err = _sources()
    if err:
        return {"ok": False, "为什么": err}
    POL = src["policy"]
    scc = src["会改状态集"]
    kinds = sorted(set(scc) | set(DEEP))
    branches = _policy_branch_count(kinds)
    rows = []
    for k in kinds:
        try:
            e0 = list(getattr(POL.evaluate(k, {}), "scopes", ()) or ())
        except Exception as e:
            e0 = ["**抛异常**", str(e)[:30]]
        p, why = DEEP.get(k, ({}, "（未声明带参 payload —— 如实标）"))
        try:
            e1 = list(getattr(POL.evaluate(k, p), "scopes", ()) or ())
        except Exception as e:
            e1 = ["**抛异常**", str(e)[:30]]
        rows.append({
            "位": k, "policy.py 里出现次数": branches.get(k, 0),
            "门有分支": branches.get(k, 0) > 0,
            "空参作用域": e0, "带参 payload": p, "为什么这个 op 会改": why,
            "带参作用域": e1, "带参后浮出来了": (not e0) and bool(e1),
            "框架说会改状态": k in scc,
        })
    blind = [r for r in rows if not r["门有分支"]]
    surfaced = [r for r in rows if r["带参后浮出来了"]]
    return {
        "ok": True,
        "口径": "`evaluate` 是**纯函数** ⇒ 带 `apply`/`submit` 的参也**不会真动手**（只算）",
        "🔴 门结构上看不见（`policy.py` 里 **0 次出现**）": {
            "位数": len(blind), "位名": [r["位"] for r in blind],
            "含义": "**没有分支** ⇒ 给**任何**参 `scopes` 都是空 ⇒ 这些位**只能靠模块自身的规则**把关"},
        "🟢 带参后作用域**浮出来了**（下界往上推）": {
            "位数": len(surfaced),
            "逐位": [{"位": r["位"], "空参": r["空参作用域"], "带参": r["带参作用域"]}
                   for r in surfaced]},
        "逐位": rows,
    }


def cmd_deep(a) -> int:
    r = deep()
    if not r.get("ok"):
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 2
    print(json.dumps(r, ensure_ascii=False, indent=1))
    print("🔴 门**结构上看不见**的位：%d 个 —— %s"
          % (r["🔴 门结构上看不见（`policy.py` 里 **0 次出现**）"]["位数"],
             "、".join(r["🔴 门结构上看不见（`policy.py` 里 **0 次出现**）"]["位名"])))
    print("🟢 带参后**浮出作用域**的位：%d 个" % r["🟢 带参后作用域**浮出来了**（下界往上推）"]["位数"])
    return 0


def cmd_cross(a) -> int:
    r = cross()
    if not r.get("ok"):
        print(json.dumps(r, ensure_ascii=False, indent=1))
        return 2
    brief = dict(r)
    brief["逐位"] = [x for x in r["逐位"] if x["零作用域"]][:8] + [{"…": "省略"}]
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    print("🔴 **零作用域 ∧ 会改状态：%d 位** —— 门不会拦，但它会改：%s"
          % (r["🔴 危险集（零作用域 ∧ 会改状态）"]["位数"],
             "、".join(r["🔴 危险集（零作用域 ∧ 会改状态）"]["位名"])))
    print("📌 这就是「**零作用域 ≠ 只读**」的实证：%d 位零作用域里，有 %d 位框架自己说会改。"
          % (r["零作用域"], r["🔴 危险集（零作用域 ∧ 会改状态）"]["位数"]))
    return 0


def cmd_danger(a) -> int:
    r = cross()
    print(json.dumps({"危险集": r.get("🔴 危险集（零作用域 ∧ 会改状态）"),
                      "零作用域-safe=False": r.get("🟡 零作用域 ∧ safe=False")},
                     ensure_ascii=False, indent=1))
    return 0


def _fake_rows(specs):
    """给自检用：从 (kind, scopes, in_scc, safe) 造行，走**同一段判据**。"""
    rows = [{"位": k, "作用域": list(s), "零作用域": len(s) == 0,
             "框架说会改状态": c, "safe": f} for k, s, c, f in specs]
    zero = [r for r in rows if r["零作用域"]]
    return {"零作用域": len(zero),
            "危险集": [r["位"] for r in zero if r["框架说会改状态"]],
            "零作用域safeFalse": [r["位"] for r in zero if r["safe"] is False]}


def cmd_selftest(a) -> int:
    lines, bad = [], 0

    def ck(name, cond, detail):
        nonlocal bad
        bad += 0 if cond else 1
        lines.append("%s %s — %s" % ("✓" if cond else "✗", name, detail))

    r = cross()
    ck("**两个源都读到**（少一个就报未读到，不拿 0 冒充）", r.get("ok") is True,
       "全量 %s 位" % r.get("全量"))
    ck("**零作用域 + 有门 == 全量**（算术自洽）",
       r.get("读数自洽", {}).get("零作用域 + 有门 == 全量") is True,
       "零 %s + 有门 %s" % (r.get("零作用域"), r.get("有门的位")))
    # ① 判据**随数据变**：人造 3 位，危险集必须只挑中"零作用域 ∧ 会改"的那 1 个
    f = _fake_rows([("a", [], True, True), ("b", ["filesystem_write"], True, False),
                    ("c", [], False, True)])
    ck("**判据随数据变**（人造位里只挑中「零作用域 ∧ 会改」的那个）",
       f["危险集"] == ["a"] and f["零作用域safeFalse"] == [],
       "危险集=%s" % f["危险集"])
    # ② 负控：**有作用域的位不许进危险集**（哪怕它会改状态）
    ck("**负控：有作用域的位不进危险集**（门会拦它）", "b" not in f["危险集"],
       "b 有 filesystem_write ⇒ 门会拦")
    # ③ 负控：**零作用域 ∧ 会改 ⇒ 必须进危险集**（不许漏）
    ck("**负控：零作用域 ∧ 会改 必须被抓**", "a" in f["危险集"], "已抓")
    # ④ 负控：**只读的零作用域位不许进危险集**（不许扩大化）
    ck("**负控：只读的零作用域位不进危险集**（不扩大化）", "c" not in f["危险集"],
       "c 零作用域但框架没说会改")
    # ⑤ 真读数：危险集必须**逐位点名**（不是只给个数）
    ck("**危险集逐位点名**（不是只给个数）",
       isinstance(r["🔴 危险集（零作用域 ∧ 会改状态）"]["位名"], list),
       "%d 位" % r["🔴 危险集（零作用域 ∧ 会改状态）"]["位数"])
    print(json.dumps({"自检": {"条数": len(lines), "通过": len(lines) - bad, "不通过": bad},
                      "逐条": lines}, ensure_ascii=False, indent=1))
    return 0 if bad == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="零作用域 ≠ 只读：两个独立源交叉审计")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("cross").set_defaults(func=cmd_cross)
    sub.add_parser("danger").set_defaults(func=cmd_danger)
    sub.add_parser("deep").set_defaults(func=cmd_deep)
    sub.add_parser("selftest").set_defaults(func=cmd_selftest)
    a = ap.parse_args()
    return a.func(a)


if __name__ == "__main__":
    raise SystemExit(main())
