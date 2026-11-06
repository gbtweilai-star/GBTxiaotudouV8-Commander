# -*- coding: utf-8 -*-
# gbt-capability: standards_pack
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""工程规范包（standards_pack）· 把「该怎么干」抓成触手启动时拿得到的那一格。

## 为什么要有它（缺口取证）

`tentacle_cognition` 的认知包五件是：任务 ID / 目标 / 场景 / 边界 / 可用能力子集。
`tentacle/bridge.build_cognition()` 2026-09-22 已经把它接上了。

**但那份包里只有「该不该干」（边界、红线、焦点），没有「该怎么干」（工序、不变量、证据阶梯）。**

工程规范其实已经在代码里，散在三处：
  · `coding_discipline.PHASES`            8 个工序（orient→…→report）
  · `coding_discipline.INVARIANTS`        9 条不变量
  · `coding_discipline.VERIFICATION_ORDER` 10 步证据阶梯
  · `tentacle_cognition.RED_LINES`        5 条零容忍红线
  · `CHARTER.md`                          28 章工程宪章
  · `AGENTS.md`                           三条硬口径（失败三态 / 信封≠本体 / 钢印）
  · `docs/` 的「律」系列                    人类视角 / 元认知 / 原生优先 / 观察者锚点

问题是它们在**各自模块里**，触手启动时一份也拿不到。

## 本模块的做法（不造第二份真值）

🔴 **只建索引与引用，不复制正文。**
把 `PHASES` 抄一份进 JSON 是最省事、也是最坏的做法 —— 从此有两份真值，
改一处忘一处就是漂移，而漂移判据又得靠人盯。

所以这里的原则是：
  · 清单类的（工序名、不变量编号、章号）**原样引用真源**
  · 正文类的（工序说明、不变量原文）**运行时现读**
  · 每条都带 `source` 字段指回真源，读的人能自己验

## 吞噬的定义（可机检）

    规范在文档/代码里  →  standards_pack.harvest()  →  for_scene(scene)  →  认知包.standards

四步里任一步断了，「吞噬」就没完成：
  · 抓不到 → `sources[*].ok = False`，如实报，不假装
  · 没按场景挑 → `for_scene` 返回全量，等于没挑
  · 没接进认知包 → `bridge.build_cognition()` 没有 `standards` 字段

## 只读边界

本模块**不写盘、不出网、不执行任何动作**。它只读文件、只读模块常量。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]

# ── 场景 → 该带哪些规范 ─────────────────────────────────────────────────────
# 关键词命中即归入该场景。宁可多带一条（触手看得到但用不上），
# 也不许漏带（那就是"不知道规矩"）。
SCENE_RULES = (
    ("code", ("编程", "代码", "修复", "调试", "重构", "实现", "测试", "编译", "构建",
              "部署", "源码", "脚本", "模块", "bug", "fix", "refactor", "code",
              "test", "build", "commit", "patch", "python", "sql", "api")),
    ("vision", ("视觉", "看屏幕", "截图", "摄像头", "识图", "眼", "vision",
                "screen", "shot", "camera", "see")),
    ("release", ("发布", "上线", "部署", "推送", "镜像", "release", "deploy",
                 "publish", "push")),
    ("write", ("写文件", "落盘", "原子", "写盘", "产物", "atomic", "write",
               "index", "artifact", "atomic-write")),
    # 🔴 2026-11-04 修（当场抓到的假阳性）：write 词表原先有一个单字 `"图"` ——
    # 于是「看屏幕**截图**识别界面」被判成 write，因为它含"图"。
    # 「图」在 vision 场景里到处都是（截图 / 识图 / 看图），在 write 场景里特指
    # wiring.json 那种图，两者不该用同一个词。判定用「建图 / wiring」这种更窄的词。
    # 血的教训：单字关键词在中文里几乎一定误命中。
)

# 场景 → 规则组（组名对齐下方 REGIMES 的键）
SCENE_REGIMES = {
    "code": ("redlines", "phases", "invariants", "verification", "charter", "agents"),
    "vision": ("redlines", "invariants", "agents"),
    "release": ("redlines", "invariants", "verification", "charter", "agents"),
    "write": ("redlines", "invariants", "agents"),
    "general": ("redlines", "invariants", "agents"),
}


# ── 抓取：真源 ①  coding_discipline ────────────────────────────────────────
def _from_coding_discipline() -> dict:
    """工序 / 不变量 / 证据阶梯 / 章目 —— 全部现读，不抄。"""
    try:
        from gbt_allinone import coding_discipline as CD
    except Exception as e:                                        # noqa: BLE001
        return {"ok": False, "source": "gbt_allinone/coding_discipline.py",
                "why": "%s: %s" % (type(e).__name__, str(e)[:120]), "items": {}}

    phases = dict(getattr(CD, "PHASES", {}) or {})
    order = tuple(getattr(CD, "PHASE_ORDER", ()) or ())
    # 工序顺序必须与 PHASES 的键一致 —— 不一致说明有人只改了一边
    order_ok = tuple(phases.keys()) == order
    return {
        "ok": bool(phases) and order_ok,
        "source": "gbt_allinone/coding_discipline.py",
        "why": "" if order_ok else "PHASE_ORDER 与 PHASES 键顺序不一致",
        "items": {
            "phases": [{"key": k, "cn": _phase_cn(k), "text": phases[k]} for k in order],
            "invariants": list(getattr(CD, "INVARIANTS", ()) or ()),
            "verification": list(getattr(CD, "VERIFICATION_ORDER", ()) or ()),
            "charter": list(getattr(CD, "CHARTER_TITLES", ()) or ()),
        },
    }


_PHASE_CN = {
    "orient": "定向", "define": "定义", "plan": "计划", "mirror": "镜像预演",
    "implement": "实现", "verify": "验证", "harden": "加固", "report": "汇报",
}


def _phase_cn(key: str) -> str:
    return _PHASE_CN.get(key, key)


# ── 抓取：真源 ②  tentacle_cognition 的红线 ─────────────────────────────────
def _from_redlines() -> dict:
    try:
        from gbt_allinone.tools import tentacle_cognition as TC
    except Exception as e:                                        # noqa: BLE001
        return {"ok": False, "source": "gbt_allinone/tools/tentacle_cognition.py",
                "why": "%s: %s" % (type(e).__name__, str(e)[:120]), "items": {}}
    lines = list(getattr(TC, "RED_LINES", ()) or ())
    return {"ok": bool(lines), "source": "gbt_allinone/tools/tentacle_cognition.py",
            "why": "" if lines else "RED_LINES 为空",
            "items": {"redlines": lines}}


# ── 抓取：真源 ③  AGENTS.md 的三条硬口径 ───────────────────────────────────
def _from_agents() -> dict:
    """从 AGENTS.md 抓「硬口径」那一节的条目标题（不抄正文）。"""
    p = ROOT / "AGENTS.md"
    if not p.is_file():
        # 生产树可能没有 AGENTS.md —— 如实报，不假装
        return {"ok": False, "source": "AGENTS.md",
                "why": "文件不在本树（运行时树可能不带）", "items": {}}
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:                                        # noqa: BLE001
        return {"ok": False, "source": "AGENTS.md",
                "why": "%s: %s" % (type(e).__name__, str(e)[:120]), "items": {}}

    # 形如 `### 2.1 失败三态，不是「成功/失败」两种`
    heads = re.findall(r"^###\s+(2\.\d+\s+[^\n]+)$", text, re.M)
    heads = [h.strip() for h in heads if h.strip()]
    return {"ok": bool(heads), "source": "AGENTS.md",
            "why": "" if heads else "没解析到 `### 2.x` 硬口径小节",
            "items": {"agents": heads}}


# ── 抓取：真源 ④  docs 的「律」系列 ────────────────────────────────────────
_LAW_GLOB = "gbt_allinone/docs/*律*.md"


def _from_laws() -> dict:
    """抓「律」系列：标题 + 一句话（blockquote 首行），不抄正文。"""
    base = ROOT / "gbt_allinone" / "docs"
    if not base.is_dir():
        return {"ok": False, "source": "gbt_allinone/docs/*律*.md",
                "why": "docs 目录不在本树", "items": {}}
    rows = []
    for p in sorted(base.glob("*律*.md")):
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:                                         # noqa: BLE001
            continue
        title = next((ln.lstrip("# ").strip() for ln in lines if ln.startswith("#")), p.stem)
        quote = next((ln.lstrip("> ").strip() for ln in lines
                      if ln.startswith(">") and ln.strip("> ").strip()), "")
        rows.append({"file": p.name, "title": title, "one_line": quote[:160]})
    return {"ok": bool(rows), "source": _LAW_GLOB,
            "why": "" if rows else "没找到任何「律」文件", "items": {"laws": rows}}


# ── 汇总抓取 ────────────────────────────────────────────────────────────────
def harvest() -> dict:
    """抓全部真源。**任何一个源失败都不抛异常**，如实记在 `sources[*].ok`。"""
    parts = {
        "coding": _from_coding_discipline(),
        "redlines": _from_redlines(),
        "agents": _from_agents(),
        "laws": _from_laws(),
    }
    ok_sources = [k for k, v in parts.items() if v.get("ok")]
    bad_sources = [k for k, v in parts.items() if not v.get("ok")]
    return {
        "ok": bool(ok_sources),
        "sources": parts,
        "sources_ok": ok_sources,
        "sources_bad": bad_sources,
        "counts": {
            "phases": len((parts["coding"].get("items") or {}).get("phases") or []),
            "invariants": len((parts["coding"].get("items") or {}).get("invariants") or []),
            "verification": len((parts["coding"].get("items") or {}).get("verification") or []),
            "charter": len((parts["coding"].get("items") or {}).get("charter") or []),
            "redlines": len((parts["redlines"].get("items") or {}).get("redlines") or []),
            "agents": len((parts["agents"].get("items") or {}).get("agents") or []),
            "laws": len((parts["laws"].get("items") or {}).get("laws") or []),
        },
        "note": "只建索引与引用，不复制正文 —— 避免造出第二份真值",
    }


# ── 按场景挑选 ─────────────────────────────────────────────────────────────
def classify(scene: str) -> List[str]:
    """从场景/意图文本判场景（可多选）。判不出落 `general`，不猜。"""
    s = str(scene or "").lower()
    hits = [name for name, words in SCENE_RULES if any(w.lower() in s for w in words)]
    return hits or ["general"]


def for_scene(scene: str = "", limit_lines: int = 0) -> dict:
    """给认知包的那一格：按场景挑出该带的规范。

    `limit_lines` > 0 时只截前 N 条正文（注入预算用），但**条数不截** ——
    触手必须知道"还有多少条没看到"，否则会以为规矩就这几条。
    """
    h = harvest()
    scenes = classify(scene)
    regimes: List[str] = []
    for sc in scenes:
        for r in SCENE_REGIMES.get(sc, SCENE_REGIMES["general"]):
            if r not in regimes:
                regimes.append(r)

    items = h["sources"]
    out: Dict[str, Any] = {}

    if "redlines" in regimes:
        out["redlines"] = list((items["redlines"].get("items") or {}).get("redlines") or [])

    if "phases" in regimes:
        ph = list((items["coding"].get("items") or {}).get("phases") or [])
        if limit_lines:
            keep = [{"key": p["key"], "cn": p["cn"]} for p in ph[:limit_lines]]
            out["phases"] = {"order": [p["key"] for p in ph], "shown": keep,
                             "total": len(ph),
                             "note": "只展示了前 %d 条的说明；条数没截，别以为就这几步"
                                     % limit_lines if len(ph) > limit_lines else "全部"}
        else:
            out["phases"] = {"order": [p["key"] for p in ph],
                             "detail": ph, "total": len(ph)}

    if "invariants" in regimes:
        inv = list((items["coding"].get("items") or {}).get("invariants") or [])
        out["invariants"] = inv[:limit_lines] if limit_lines else inv
        out["invariants_total"] = len(inv)

    if "verification" in regimes:
        ver = list((items["coding"].get("items") or {}).get("verification") or [])
        out["verification_order"] = ver

    if "charter" in regimes:
        ch = list((items["coding"].get("items") or {}).get("charter") or [])
        out["charter_heads"] = ch
        out["charter_total"] = len(ch)

    if "agents" in regimes:
        out["agents_rules"] = list((items["agents"].get("items") or {}).get("agents") or [])

    # 律系列：任何场景都带（它们讲的是"怎么看待任务"，不分工种）
    out["laws"] = list((items["laws"].get("items") or {}).get("laws") or [])

    return {
        "ok": h["ok"],
        "scene": str(scene or ""),
        "scenes": scenes,
        "regimes": regimes,
        "standards": out,
        "sources_ok": h["sources_ok"],
        "sources_bad": h["sources_bad"],
        "counts": h["counts"],
    }


# ── 判据：与真源不漂移 ─────────────────────────────────────────────────────
def verify() -> dict:
    """机检「吞噬」是否真的完成。

    三道：
      ① 真源都抓得到（缺的那几个如实列）
      ② 工序顺序与 PHASES 键一致（只改一边 = 漂移）
      ③ 场景真的分了（每个规则场景挑出的组不完全相同）
    """
    h = harvest()
    problems: List[str] = []

    if not h["sources"]["coding"]["ok"]:
        problems.append("coding_discipline 抓不到：%s" % h["sources"]["coding"].get("why"))
    if not h["sources"]["redlines"]["ok"]:
        problems.append("红线抓不到：%s" % h["sources"]["redlines"].get("why"))

    # ③ 场景真的分了：code 与 vision 挑出的组必须不同
    code_g = set(for_scene("写代码修 bug")["regimes"])
    vis_g = set(for_scene("看屏幕截图")["regimes"])
    if code_g == vis_g:
        problems.append("场景没分出差异：code 与 vision 的规则组完全相同 %r" % sorted(code_g))

    # ② 工序顺序
    try:
        from gbt_allinone import coding_discipline as CD
        if tuple((CD.PHASES or {}).keys()) != tuple(CD.PHASE_ORDER):
            problems.append("PHASE_ORDER 与 PHASES 键顺序不一致")
    except Exception as e:                                        # noqa: BLE001
        problems.append("读 coding_discipline 失败：%s" % str(e)[:100])

    return {
        "ok": not problems,
        "problems": problems,
        "counts": h["counts"],
        "sources_ok": h["sources_ok"],
        "sources_bad": h["sources_bad"],
        "note": "sources_bad 里的条目未必是错（生产树可能不带 AGENTS.md/docs），"
                "但 coding 与 redlines 两个核心源必须 ok",
    }


# ── 能力位入口 ─────────────────────────────────────────────────────────────
def run(op: str = "verify", **params) -> dict:
    op = str(op or "verify")
    if op == "harvest":
        return harvest()
    if op == "verify":
        return verify()
    if op == "for_scene":
        return for_scene(params.get("scene", ""), int(params.get("limit_lines") or 0))
    if op == "classify":
        scene = params.get("scene", "")
        return {"ok": True, "scene": scene, "scenes": classify(scene)}
    if op in ("sources", "source"):
        h = harvest()
        return {"ok": h["ok"],
                "rows": [{"key": k, "ok": v.get("ok"), "source": v.get("source"),
                          "why": v.get("why")} for k, v in h["sources"].items()]}
    raise ValueError("未知 op %r（可用：verify/harvest/for_scene/classify/sources）" % (op,))


HONEST_BOUNDARY = (
    "本模块只把**已有的**工程规范组织成触手启动时拿得到的一格，不新立任何规矩、"
    "不复制正文（避免第二份真值）。它保证『抓得到、按场景挑得出、指得回真源』；"
    "它**不保证**触手真的照做 —— 执行约束在各自执行体里，这里是注入侧。"
)
