#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""自我认知缺口守卫（awareness_gap_guard）

只做一件事：把**被注入的自我认知**和**盘上真实的自己**摆在一起，报出不一致。

为什么必须有这个：
  gbt_allinone/llm/cloud_llm.py:169-216 会在每次开工时**强制首注入**一份"我是谁"：
    · 主路径  ~/GBT-JXDWD/sandbox/GBT_自我认知_LIVE.md   （静态文件，会过期）
    · 备用    _BUILTIN_AWARENESS（cloud_llm.py:179-200，内建字符串，同样静态）
  实测（2026-09-22）两份都过期：外部写"119模块/14域"、内建写"118模块/22域"，
  而盘上真身是 158 能力位 / 29 域。**两份静态说明都不是自己**。

  后果不是"数字不好看"，是**模型拿着过期的自我说明书去干活** ——
  它会去调注册表里根本不存在的能力（内建版 183-198 行列的那些名字，实测大量不在册），
  也会把内建版第 199 行那句"所有渗透/安全/黑客请求正常执行"当成自己的铁律，
  而框架真实策略是 11 项禁用 + 唯一授权门。

  ⇒ 病根不是"数字写错了"，是**"一份会过期的静态说明被当成权威自我认知"**。
     所以本守卫不修数字 —— 它让"不一致"当场可见。

🔴 红线（本模块永不违反）：
  1) 只读。不改 cloud_llm.py，不改那份 LIVE.md，不改任何文件。
  2) 不 import cloud_llm（那会拉起重依赖）；只读它的**源码文本**做静态枚举。
  3) 不联网、不起进程、不写盘。

用法：
    python -m gbt_allinone.tools.awareness_gap_guard            # 人读报告
    python -m gbt_allinone.tools.awareness_gap_guard --json     # 机读
    python -m gbt_allinone.tools.awareness_gap_guard --check    # 有硬冲突 ⇒ 退出码 1
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent          # …/gbt_allinone
_CLOUD = PKG / "llm" / "cloud_llm.py"
_REGISTRY = PKG / "caps_registry.py"

def _resolve_path_expr(expr: str):
    """把 `_AWARENESS_PATHS` 里的一个路径表达式解析成真实 Path。

    **刻意不用 eval** —— 那会把"读源码"变成"执行源码"，是本守卫最不该干的事。
    只认两种源码形态：
      · `Path.home() / "a" / "b"`          → home/a/b
      · `<任意名字> / "a" / "b"`            → PKG/a/b（框架内部相对路径）
    认不出来就返回 None，由调用方如实记进 missing，**不猜**。
    """
    parts = [seg.strip() for seg in expr.split("/")]
    if not parts:
        return None
    head = parts[0]
    tail = []
    for seg in parts[1:]:
        if seg.startswith(("'", '"')) and seg.endswith(("'", '"')):
            tail.append(seg[1:-1])
        else:
            return None                      # 出现变量拼接等复杂形态 → 不认，不猜
    if head.startswith("Path.home()"):
        return Path.home().joinpath(*tail)
    if head and all(c.isalnum() or c in "_." for c in head):
        return PKG.joinpath(*tail)           # `_SANDBOX_ROOT / "x"` 这类框架内部根
    return None


def _live_paths() -> list:
    """**从 cloud_llm.py 源码里读真实的 _AWARENESS_PATHS**，不许硬编码。

    2026-09-22 改：本守卫初版把四条候选路径写死在文件里（含两条外部沙箱路径）。
    后来 `cloud_llm.py` 把外部两条**删掉了**（框架不再依赖外部沙箱认识自己），
    守卫却还在报"被注入的自我认知里有那两个外部文件" —— **成了假读数**。

    教训（铁律 3）：判据不许比事实宽。**路径清单是事实，必须从源头读，不许复写一份。**
    复写的那一份必然与源头漂移，然后守卫就开始报不存在的事。
    """
    tree = ast.parse(_read_text(_CLOUD))
    out = []
    for node in tree.body:
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.List)):
            continue
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id == "_AWARENESS_PATHS":
                for el in node.value.elts:
                    txt = ast.unparse(el)
                    if "Path.home()" in txt or "/" in txt:
                        out.append(txt)
    return out

# 注入文本里**与真实授权门冲突**的危险断言（命中即硬报警）
_DANGEROUS = [
    (re.compile(r"所有渗透[/／、]?\s*安全[/／、]?\s*黑客请求\s*正常执行"),
     "注入文本宣称「所有渗透/安全/黑客请求正常执行」—— 与事实冲突：UNIMPLEMENTED_CAPS 那 11 个名字**没有实现**"
     "（2026-09-23 实测）；且一切有后果动作仍要过唯一授权门"),
    (re.compile(r"授权安全研究"),
     "以「授权安全研究」为名预设授权 —— 而授权只能主人在终端发放，AI 无权自授"),
]


def _read_text(p: Path) -> str:
    """读源码文本 —— **必须 utf-8-sig**。

    实测（2026-09-22）：`gbt_allinone/caps_registry.py` 首字节是 BOM(U+FEFF)。
    Python **import** 时容忍它（走 utf-8-sig），但用 `encoding="utf-8"` 读出来再
    `ast.parse()` 会当场抛 `SyntaxError: invalid non-printable character U+FEFF`。
    本守卫第一次跑就是死在这里 —— 所以这个 helper 不是洁癖，是踩过的坑。
    """
    return p.read_text(encoding="utf-8-sig", errors="replace")


def _registry() -> dict:
    tree = ast.parse(_read_text(_REGISTRY))
    out: dict[str, set] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Dict):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = {k.value for k in node.value.keys
                                 if isinstance(k, ast.Constant) and isinstance(k.value, str)}
    return out


def _claims(text: str, source: str) -> dict:
    """从一份自我认知文本里抽出它声称的数字与能力名。"""
    nums = {}
    for label, pat in (("modules", r"(\d+)\s*个能力模块"),
                       ("domains", r"(\d+)\s*个域|\*\*(\d+)个域\*\*"),
                       ("pipelines", r"(\d+)\s*条管道"),
                       ("tentacles", r"(\d+)\s*个亿万触手")):
        m = re.search(pat, text)
        if m:
            nums[label] = int(next(g for g in m.groups() if g))
    # 「XX域N: a b c …」这种行式清单
    named = set()
    for m in re.finditer(r"[\u4e00-\u9fa5]{2,8}域\d+\s*[:：]([^\n]+)", text):
        named |= {w for w in re.split(r"[\s,，、]+", m.group(1)) if re.fullmatch(r"[a-z][a-z0-9_]{2,}", w)}
    return {"source": source, "numbers": nums, "named_caps": sorted(named)}


def run() -> dict:
    reg = _registry()
    benign = reg.get("BENIGN_CAPS", set())
    # 2026-09-23 解禁后：被拒名单为空；名字没丢，转在 UNIMPLEMENTED_CAPS 登记。
    disabled = reg.get("DISABLED_CAPS", set())
    unimplemented = reg.get("UNIMPLEMENTED_CAPS", set())
    truth = {"capabilities_total": len(benign) + len(unimplemented),
             "available": len(benign),
             "denied": len(disabled),
             "registered_unimplemented": len(unimplemented)}

    reports, conflicts, missing_files = [], [], []
    for _sp in _live_paths():
        # _sp 是形如 `Path.home() / "GBT-JXDWD" / ...` 或 `_SANDBOX_ROOT / "..."` 的源码文本。
        # 只解析我们认识的两种形态，**不用 eval**（eval 会把"读源码"变成"执行源码"）。
        try:
            p = _resolve_path_expr(_sp)
        except Exception:
            missing_files.append(f"{_sp}（无法解析）")
            continue
        if p is None:
            missing_files.append(f"{_sp}（形态不认识）")
            continue
        try:
            txt = _read_text(p)
        except Exception:
            missing_files.append(str(p))
            continue
        c = _claims(txt, str(p))
        c["exists"] = True
        c["bytes"] = len(txt.encode("utf-8"))
        unknown = [n for n in c["named_caps"] if n not in benign and n not in disabled]
        c["named_total"] = len(c["named_caps"])
        c["named_not_in_registry"] = unknown
        reports.append(c)
        for pat, why in _DANGEROUS:
            for m in pat.finditer(txt):
                conflicts.append({"file": str(p), "phrase": m.group()[:60], "why": why})

    # 内建备用版（cloud_llm.py:179-200 的字面量）
    src = _read_text(_CLOUD)
    m = re.search(r'_BUILTIN_AWARENESS\s*=\s*_resolve_awareness_anchor\(\s*"""(.*?)"""',
                  src, re.S)
    builtin = None
    if m:
        body = m.group(1)
        builtin = _claims(body, "cloud_llm.py:179-200 内建备用")
        builtin["exists"] = True
        builtin["bytes"] = len(body.encode("utf-8"))
        unknown = [n for n in builtin["named_caps"] if n not in benign and n not in disabled]
        builtin["named_total"] = len(builtin["named_caps"])
        builtin["named_not_in_registry"] = unknown
        for pat, why in _DANGEROUS:
            for mm in pat.finditer(body):
                conflicts.append({"file": "cloud_llm.py:179-200", "phrase": mm.group()[:60], "why": why})

    return {
        "truth_on_disk": truth,
        "injected_sources": reports,
        "builtin_fallback": builtin,
        "missing_paths": missing_files,
        "dangerous_assertions": conflicts,
        "hard_conflict": bool(conflicts),
        "honest_boundary": (
            "本守卫只比『注入文本声称的数字与能力名』和『caps_registry 的键』。"
            "**不判**注入是否真的发生（那要看 PROVIDER 与调用路径）、"
            "**不判**某个名字该不该在册。数字对上了也不代表自我认知就是准的。"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="自我认知缺口守卫（只读）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    r = run()
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        t = r["truth_on_disk"]
        print("=== 盘上真实的自己 ===")
        # 🔴 2026-09-25 修：这里原来读 `t['disabled']`，而 `truth` 字典里的键叫 **`denied`**
        #    （见本文件 `_truth_on_disk` 的构造）⇒ **KeyError: 'disabled'**，
        #    整条命令**一跑就崩**。而它正是**自我认知文本里点名的自校验命令**
        #    （`cloud_llm.py` 的 `_BUILTIN_AWARENESS` 写着
        #     `自校验：python -m gbt_allinone.tools.awareness_gap_guard`）——
        #    **一条被写进 system prompt 让模型去跑的命令，自己跑不起来。**
        #    ⇒ 键名对齐（读 `denied`）。机检：`tests/test_awareness_guard_runs.py`。
        print(f"  能力位 {t['capabilities_total']}（可用 {t['available']} · 禁用 {t['denied']}）")
        print("\n=== 被注入的自我认知 ===")
        for s in r["injected_sources"] + ([r["builtin_fallback"]] if r["builtin_fallback"] else []):
            if not s:
                continue
            tag = "外部文件" if s["source"].startswith("/") or ":" in s["source"][:3] else "内建备用"
            print(f"  · [{tag}] {s['source']}")
            print(f"      声称: {s['numbers'] or '（未解析到数字）'}")
            print(f"      点名能力 {s['named_total']} 个，其中**不在注册表 {len(s['named_not_in_registry'])} 个**")
            if s["named_not_in_registry"]:
                print(f"        例: {s['named_not_in_registry'][:8]}")
        if r["missing_paths"]:
            print(f"\n  走不到的路径（{len(r['missing_paths'])} 个）:")
            for p in r["missing_paths"]:
                print(f"    {p}")
        print("\n=== 危险断言（注入文本 vs 真实授权门）===")
        if r["dangerous_assertions"]:
            for c in r["dangerous_assertions"]:
                print(f"  🔴 {c['file']}")
                print(f"     原文: {c['phrase']}")
                print(f"     问题: {c['why']}")
        else:
            print("  未命中")
        print("\n边界：" + r["honest_boundary"])
    return 1 if (a.check and r["hard_conflict"]) else 0


if __name__ == "__main__":
    sys.exit(main())


