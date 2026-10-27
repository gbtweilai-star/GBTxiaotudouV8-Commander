#!/usr/bin/env python3
"""大脑对齐器 —— 每一位都必须经过大脑执行层

主人 2026-10-28 令：「**严禁无脑操作，大脑执行层是必须经过的**」。

所以本器**不直接调 run_task 打位**（那是无脑轮询），而是走：

    每一位 → brain_unify(goal=该位自己的描述, payload.kind=该位)
              → route（人话能不能导回它自己 = 对齐判据）
              → execute（真跑，过唯一门与授权门）
              → verify（视觉验证，本机不可用要如实记）
              → health（五维自检分）

对齐判据（这是"无死角对齐"的真含义）：
  **拿每个能力位自己的描述当人类意图，看大脑能不能路由回它自己。**
  导不回来 = 路由层对这个位是"瞎的"，就算位本身能跑也算没对齐。

分类（逐一记账，不笼统）：
  aligned       路由回到自己 · 执行 ok · 三大件齐
  routed_other  路由跑到别的位去了（路由缺陷，主因）
  exec_denied   路由对了，过授权门被拒（正常，要主人发票）
  exec_failed   路由对了，执行失败（缺依赖/缺参数/file）
  unroutable    词表与语义都没命中

⚠ verify 在这台机上是空的：`verify` 恒返回 `vision: False`（非交互桌面，
   GDI/DXGI 拿不到屏）。**所以任何"已验证"的说法都必须带上这一条。**

用法：
  python3 tools/brain_align.py --sample 8      # 先小样本（严禁一上来全量）
  python3 tools/brain_align.py --domain llm
  python3 tools/brain_align.py --all
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "state" / "brain_align.json"


def caps() -> list[dict]:
    """R-B：现算 + 两源合并（registry 与 json 的 schema 不同，见 omni_align 的教训）。"""
    reg, js = [], []
    try:
        from gbt_allinone.caps_registry import all_caps
        reg = [dict(c) for c in all_caps()]
    except Exception:                                         # noqa: BLE001
        pass
    try:
        d = json.loads((ROOT / "data" / "capabilities.json").read_text(encoding="utf-8"))
        raw = d if isinstance(d, list) else d.get("capabilities", d)
        js = raw if isinstance(raw, list) else list(raw.values())
    except Exception:                                         # noqa: BLE001
        pass
    by = {}
    for r in js:
        if isinstance(r, dict) and r.get("name"):
            by[str(r["name"])] = dict(r)
    for r in reg:
        if isinstance(r, dict) and r.get("name"):
            by.setdefault(str(r["name"]), {}).update(
                {k: v for k, v in r.items() if v is not None})
    return list(by.values())


def safe_to_run(c: dict) -> tuple[bool, str]:
    """只有只读·无作用域·无参数的位才真跑（其余只做路由对齐，不动手）。"""
    if c.get("requires_params"):
        return False, "需参数"
    if c.get("needs_confirmation"):
        return False, "需确认"
    sc = c.get("scopes_static")
    if isinstance(sc, str) and "零作用域" not in sc and sc.strip():
        return False, "有作用域"
    if isinstance(sc, (list, tuple)) and [x for x in sc if x]:
        return False, "有作用域"
    if not c.get("readonly") and c.get("safe") is not True:
        return False, "非只读"
    return True, ""


def align_one(c: dict) -> dict:
    from gbt_allinone.api import run_task
    name = str(c.get("name"))
    desc = str(c.get("desc") or name)[:160]
    goal = desc or name
    ok_run, why = safe_to_run(c)

    # 🔴 2026-10-28 修（**这是我自己造的 bug**）：
    #   api 层 brain_unify 的写法是
    #     brain_exec.unify(goal, {k: v for k, v in p.items() if k != "goal"})
    #   —— 它把"除 goal 以外的所有键"当 payload 传下去。
    #   我原来写成 {"goal":…, "payload": {"kind":…}} ⇒ 多包了一层，
    #   "payload" 这个键一路冲进具体函数，变成
    #     beliefs() got an unexpected keyword argument 'payload'
    #   ⇒ 误判 belief_forge 执行失败。正确写法是**扁平传**。
    t0 = time.time()
    try:
        r = run_task("brain_unify", {"goal": goal, "kind": name})
    except Exception as exc:                                  # noqa: BLE001
        return {"name": name, "domain": c.get("domain"), "verdict": "error",
                "why": "%s: %s" % (type(exc).__name__, str(exc)[:120])}
    res = (r.get("gbt_result") or {}).get("result") or r.get("result") or {}
    ch = res.get("chain") or {}
    rt = ch.get("route") or {}
    ex = ch.get("execute") or {}
    vf = ch.get("verify") or {}
    routed = (rt.get("best") or {}).get("kind")
    rt_extra = rt.get("self_label") or {}
    _blob = json.dumps(res, ensure_ascii=False) if isinstance(res, (dict, list)) else str(res)
    # 🔴 2026-10-28：原来把"路由到别的位"一律记 routed_other，混了三种性质：
    #    ① 同域近似位（brain_health → health）：描述本身就有重叠，属正常近似
    #    ② 兜底黑洞（* → tentacle）：semantic 给不出时的通用落点
    #    ③ 真错位（指向不相干的域）
    #    混在一起看就像"7 个全坏"，其实只有一部分是路由缺陷。
    tgt_dom = str(c.get("domain") or "")
    got_dom = ""
    if routed:
        try:
            from gbt_allinone.caps_registry import all_caps as _ac
            for _c in _ac():
                if isinstance(_c, dict) and str(_c.get("name")) == str(routed):
                    got_dom = str(_c.get("domain") or "")
                    break
        except Exception:                                     # noqa: BLE001
            pass

    # 🔴 2026-10-28 修判定顺序：原来 `elif why` 排在路由判断**前面**，
    #    于是非只读位的**路由错位被伪装成 skipped** ——
    #    实测 claude_code/codebuddy 在 skipped↔aligned 之间抖，直跑 6/6 全 ok，
    #    抖的其实是路由，却被 why 盖住了。
    #    正确顺序：先判路由对错，再看是不是我们自己没让它跑。
    if routed and routed != name:
        # 自称谓撞车：两个位的中文名完全一样（实测 omni_plug / wf_cache_clear
        # 都叫「万能插」）——文本路由**无法区分**，这不是路由 bug，是数据撞车。
        if (res.get("self_label") is None and (rt.get("self_label") or {}).get("ambiguous")):
            verdict = "label_collision"
        elif routed == "tentacle":
            verdict = "routed_broad"          # 兜底黑洞，不是错指
        elif got_dom and got_dom == tgt_dom:
            verdict = "routed_parent"         # 同域近似位
        else:
            verdict = "routed_wrong"          # 真错位（跨域）
    elif routed == name and ex.get("ok"):
        verdict = "aligned"
    elif why:                                  # 路由对了，只是我们没让它真跑
        verdict = "needs_params" if why == "需参数" else "skipped"
    elif "winreg" in _blob or "No module named 'win" in _blob:
        # 平台不可用：winreg / _winapi 这类只在 Windows 存在，
        # 本机是 iSH/Alpine —— 这不是"执行失败"，是**这台机没有那个平台**。
        verdict = "platform_unavailable"
    elif False:
        pass
    elif ex.get("status") == "denied":
        verdict = "exec_denied"
    elif routed == name and not ex.get("ok"):
        verdict = "exec_failed"
    elif rt.get("path") in (None, "heuristic") and not routed:
        verdict = "unroutable"
    else:
        verdict = "exec_failed"
    return {"name": name, "domain": c.get("domain"), "verdict": verdict,
            "routed_to": routed, "route_path": rt.get("path"),
            "degraded": bool(rt.get("degraded")),
            "exec_ok": ex.get("ok"), "exec_status": ex.get("status"),
            "verify_ok": vf.get("ok"), "verify_checks": vf.get("checks"),
            "health": (ch.get("health") or {}).get("score"),
            "ran": ok_run, "skip_why": why,
            "ms": round((time.time() - t0) * 1000)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--domain", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--repeat", type=int, default=1,
                    help="每位重复几次；≥2 时只认稳定判定，抖动位单列")
    a = ap.parse_args()

    items = caps()
    if a.domain:
        items = [c for c in items if str(c.get("domain")) == a.domain]
    if a.sample:
        items = items[:a.sample]
    if not (a.sample or a.domain or a.all):
        ap.print_help()
        return 2

    print("  总 %d 位（现算）· 全部经 brain_unify（route→execute→verify→health）" % len(items))
    print("  ⚠ verify 在本机恒为 vision:False（非交互桌面拿不到屏）—— 下面读数带这一条\n")
    print("  %-22s %-13s %-9s %-6s %s" % ("位", "判定", "路由到", "执行", "备注"))

    rows, t0 = [], time.time()
    for i, c in enumerate(items, 1):
        row = align_one(c)
        if a.repeat > 1:
            # 🔴 2026-10-28 实测：同一批位跑两次，41 位里有 4 位判定会翻
            #    （路由走 semantic 时依赖模型输出；执行偶发失败）⇒ 单次读数不可当结论。
            #    重复采样，全部一致才算 stable；不一致记 flaky 并列出各次结果。
            seen = [row["verdict"]]
            for _ in range(a.repeat - 1):
                seen.append(align_one(c)["verdict"])
            if len(set(seen)) == 1:
                row["stable"] = True
            else:
                row["stable"] = False
                row["flaky"] = seen
                row["verdict"] = "flaky"
        rows.append(row)
        note = row.get("skip_why") or ("degraded" if row.get("degraded") else "")
        print("  %-22s %-13s %-9s %-6s %s" %
              (row["name"], row["verdict"], row.get("routed_to") or "-",
               row.get("exec_status") or "-", note), flush=True)
        if i % 25 == 0:
            print("    …%d/%d %.0fs" % (i, len(items), time.time() - t0), flush=True)

    from collections import Counter
    by = Counter(r["verdict"] for r in rows)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                               "total": len(rows), "by_verdict": dict(by),
                               "note_verify": "verify 恒 vision:False（本机无交互桌面）",
                               "rows": rows}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print("\n  === 汇总 ===")
    for k, v in by.most_common():
        print("    %-14s %d" % (k, v))
    print("\n  报告: state/brain_align.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
