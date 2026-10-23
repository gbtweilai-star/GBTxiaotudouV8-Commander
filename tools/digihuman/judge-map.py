# -*- coding: utf-8 -*-
r"""数字人链 · 判据面清点（judge-map）—— **哪些阶段真有机检、哪些只有人眼、哪些恒真**。

主人令目标（2026-10-10 目标轮）：「③ 整体没完善就不停工」
—— 但"整体有没有完善"要**看得见**才谈得上不停工。本件就是那张表。

## 凭什么算数（自动分型，不靠我手填）
逐阶段拿它 gate 的**源码**（inspect.getsource），按**里面调用了哪个判据函数**分型：
  · gate_hf_check / gate_video / gate_motion / gate_clarity / gate_render / gate_rig /
    gate_size / gate_exists / gate_sub  ⇒ **机检**（有真读数）
  · gate_review / tpose-check（人工确认记录）  ⇒ **人眼**（要人看过、绑哈希）
  · 硬编码 True/False 的 lambda  ⇒ **恒真/恒假**（等于没有判据）
  · 取不到源码 ⇒ **未知**（如实标，不猜）
**注意**：分型只说明"这道门用了什么手段"，**不说明它判得对不对** ——
判得对不对要靠它自己的负控（本仓律：判据没有负控就是摆设）。

用法：py -3.14 -X utf8 tools/digihuman/judge-map.py [--json]
"""
from __future__ import annotations

import argparse
import inspect
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MACHINE = ("gate_hf_check", "gate_video", "gate_motion", "gate_clarity", "gate_render",
           "gate_rig", "gate_size", "gate_exists", "gate_sub", "gate_assets",
           "gate_creative", "gate_glb_refs")
EYE = ("gate_review", "tpose-check", "人工确认", "S2-human-ok")
KNOWN_NEG = {
    "gate_review": "2026-10-10 挪走渲染图 ⇒ 三层同时报缺（实测）",
    "gate_motion": "2026-10-10 换回死帧 ⇒ 判红（实测）",
    "gate_hf_check": "2026-10-10 改工程一个字节 ⇒ 判决作废（实测）",
    "gate_clarity": "2026-10-10 缺渲染图 ⇒ 报缺（实测）",
    "gate_render": "2026-10-10 改 rig 一个字节 ⇒ 渲染失效（实测）",
}


def _candidate_files(src: str, funcs: list) -> list:
    """**顺着 gate 源码里的 .py 路径去找真判据件** —— 这才是关键的一步。

    🔴 我第一版只按「判据函数定义在哪个文件」找 ⇒ 全部 gate_* 都定义在 pipeline.py 里
      ⇒ 一律报 pipeline.py 无 selftest ⇒ **等于没查**。
      真正的判据在 gate **委托**的那个件里（例：gate_sub("tools/digihuman/tpose-check.py", ...)）
      ⇒ 必须把源码里出现的 **.py 路径**也当候选。
    """
    cands = []
    for m in re.finditer(r'["\']([^"\']*?\.py)["\']', src):
        rel = m.group(1).replace("\\", "/")
        p = (ROOT / rel) if not Path(rel).is_absolute() else Path(rel)
        if p.is_file():
            cands.append(p)
    for f in funcs:                                   # 再带上判据函数自己的源文件（两者都查）
        fn = _GATE_FUNCS.get(f)
        if fn is None:
            continue
        try:
            sp = inspect.getsourcefile(fn)
        except Exception:                                             # noqa: BLE001
            continue
        if sp and Path(sp).is_file():
            cands.append(Path(sp))
    seen, uniq = set(), []
    for p in cands:
        r = str(p.resolve())
        if r not in seen:
            seen.add(r); uniq.append(p)
    return uniq


def probe_negatives(funcs: list, src: str = "") -> list:
    """**自己去把负控找出来并真跑**，而不是等我手填。

    🔴 2026-10-10 为什么补这一刀：第一版把负控写成硬编码表 ⇒ 表里没列的阶段一律显示「未记录」。
    但 S2 的剪影判据其实**有 selftest（3 条负控）**，只是它在 tpose-check.py 里、不在 gate 源码里
    ⇒ **judge-map 看不见它** ⇒ 于是"有负控"和"没负控"在表上长得一模一样。
    ==一张分不清这两者的表，比没有表更坏==（本仓律：判据没有负控就是摆设 —— 那就得先能看出谁有）。
    做法：顺着判据函数找到它所在**文件**，看那个文件有没有 selftest（或 --selftest），**有就真跑一次**。
    """
    import subprocess as _sp
    out = []
    for p in _candidate_files(src, funcs):
        body = p.read_text(encoding="utf-8", errors="replace")
        has = ("def selftest" in body) or ("--selftest" in body)
        if not has:
            out.append("%s: **无 selftest**" % p.name)
            continue
        # 🔴 2026-10-10 自纠：探针原来只会 --selftest（开关），而 gates.py 认的是 selftest
        #    （**子命令**）⇒ 探针把它跑成"未知子命令" rc=2，**误报成失败**。
        #    ==探针自己也会假红 —— 两种写法都试，取第一个不是"用法错(rc=2)"的。==
        try:
            rc, tail = None, []
            for form in ("selftest", "--selftest"):
                cp = _sp.run([sys.executable, "-X", "utf8", str(p), form],
                             capture_output=True, timeout=600, cwd=str(ROOT))
                rc = cp.returncode
                tail = ((cp.stdout or b"") + (cp.stderr or b"")).decode("utf-8", "replace").strip().splitlines()
                if rc != 2:                       # rc=2 = 这个件不认这种写法，换下一种
                    break
            # rc=3 是本仓约定的「**不适用（缺前置）**」—— 与「失败」必须分开念，
            # 否则要服务的判据（如 S11 的运行时门）永远显示成"失败"，读数就糊了。
            verdict = ("**通过**" if rc == 0 else
                       "**不适用（缺前置，rc=3）**" if rc == 3 else
                       "**失败(rc=%s)**" % rc)
            out.append("%s: selftest %s · %s"
                       % (p.name, verdict, (tail[-1][:60] if tail else "")))
        except Exception as e:                                        # noqa: BLE001
            out.append("%s: selftest 跑不起来 %s" % (p.name, type(e).__name__))
    return out or ["**未记录**"]


_GATE_FUNCS: dict = {}


def classify(src: str) -> tuple:
    """按源码里出现的判据函数名分型。**只认函数名，不认注释**。"""
    code = re.sub(r"#[^\n]*", "", src)
    # 🔴 2026-10-10 自纠：MACHINE 原来是我**手维护**的名单 ⇒ 我一加新门（gate_publish）它就漏，
    #    当场把 S7 从「文件存在性」退回成「未知」。==手维护的名单一定会漂。==
    #    ⇒ 改成**现算**：模块里所有 gate_* 函数一律算机检（它们都在 _GATE_FUNCS 里）。
    machine = set(MACHINE) | set(_GATE_FUNCS)
    hit_m = [m for m in sorted(machine) if m in code]
    hit_e = [m for m in EYE if m in code]
    if hit_m and hit_e:
        return "机检+人眼", hit_m + hit_e
    if hit_m:
        return "机检", hit_m
    if hit_e:
        return "人眼", hit_e
    if re.search(r"lambda:\s*\(\s*(True|False)\s*,", code):
        return "**恒真/恒假（等于没判据）**", []
    # 🔴 2026-10-10 补这一类：视频链 S7 的门是 lambda: (LEDGER.exists(), ...) —— 只查"账本在不在"。
    #    原文落到最后一行报「未知」，而它其实**不是未知**：形状很清楚，**只是很弱**。
    #    ==把"弱"和"看不懂"混成一格，表就失去了指向性。==
    if ".exists()" in code:
        return "**文件存在性（只查在不在，不查内容）**", []
    return "未知（取不到源码？）", []


def main() -> int:
    ap = argparse.ArgumentParser(description="编排器判据面清点（可指任意一条链）")
    ap.add_argument("--json", action="store_true")
    # 🔴 2026-10-10 泛化：本件原先是数字人链专用；视频链是同一种 STAGES+gate_* 形状，
    #    而它**更早**就踩过"三个阶段是恒真门"的坑（我自己修过）⇒ 那张表也该能一眼看穿。
    ap.add_argument("--pipeline", default="tools/digihuman/pipeline.py",
                    help="要清点的编排器（默认数字人链）")
    a = ap.parse_args()
    import importlib.util as _u
    p = Path(a.pipeline)
    if not p.is_absolute():
        p = ROOT / p
    if not p.is_file():
        print("找不到 %s" % p); return 1
    sp = _u.spec_from_file_location("_jmpl", p)
    pl = _u.module_from_spec(sp)
    sp.loader.exec_module(pl)
    # 把 pipeline 模块里所有 gate_* 判据函数登记进 _GATE_FUNCS（供 probe_negatives 顺藤摸瓜找件）
    for _n in dir(pl):
        if _n.startswith("gate_"):
            _GATE_FUNCS[_n] = getattr(pl, _n)
    rows = []
    for st in pl.STAGES:
        try:
            src = inspect.getsource(st["gate"])
        except Exception as e:                                        # noqa: BLE001
            src = ""
            kind, funcs = "未知（%s）" % type(e).__name__, []
        if src:
            kind, funcs = classify(src)
        try:
            ok, note = st["gate"]()
        except Exception as e:                                        # noqa: BLE001
            ok, note = False, "门异常 %s" % type(e).__name__
        # 负控：**先看已实测表，再去判据件里找 selftest 并真跑**（两处都记）
        neg = [KNOWN_NEG[f] for f in funcs if f in KNOWN_NEG] or probe_negatives(funcs, src)
        rows.append({"阶段": st["id"], "名称": st["name"], "能力位": st.get("cap") or "—",
                     "判据类型": kind, "判据": funcs or [],
                     "实测": "OK" if ok else "红", "读数": str(note)[:96],
                     "负控出处": neg or ["未记录"]})
    if a.json:
        print(json.dumps({"逐阶段": rows}, ensure_ascii=False, indent=1))
        return 0
    print("%s · 判据面清点（自动分型：看 gate 源码里调了哪个判据函数）"
          % p.parent.name + "/" + p.name)
    print("%-5s %-15s %-13s %-12s %-4s %s" % ("阶段", "名称", "能力位", "判据类型", "实测", "负控出处"))
    print("-" * 106)
    for r in rows:
        print("%-5s %-15s %-13s %-12s %-4s %s"
              % (r["阶段"], r["名称"][:13], str(r["能力位"])[:11], r["判据类型"],
                 r["实测"], (r["负控出处"][0])[:32]))
    from collections import Counter
    c = Counter(r["判据类型"] for r in rows)
    print()
    print("分型统计: " + " · ".join("%s %d" % (k, v) for k, v in c.most_common()))
    print("口径: 分型只说明**用了什么手段**，不说明判得对不对；判得对不对看它自己的负控。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
