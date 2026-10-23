# -*- coding: utf-8 -*-
# GBT小土豆V8 永久钢印 · 开发者：自由的风 · 守护者：公主土豆
"""showcase_ops —— 作品解剖与展示（主人令 2026-10-16：让每一次的作品都能完美的展示能力）

蒸自 **wheresryan22/anatomy**（MIT · 13,459 星 · topics: agent-skill/svg/vizualization）的**思路与架构**：
  **"用一个真会动的实物来讲解一个概念"** —— 概念 → 会动的实物（例：cache key ⇒ 弹子锁；
  一个 GPU context 服务多画布 ⇒ 龙门绘图仪）→ **几十个小而精确的零件**（SVG + WebGL 着色器 + 3D）
  → 放进**带标题/提示/实时读数**的画框卡片 → 指针与键盘下**平静地动** → **放大每个关节自检**
  → **图里显示的每个数字都来自驱动零件运动的同一个小模型**（读数同源）。
我们加的三条护栏：署名必在 · 未验标未验 · 读数必须能指回模型或能力位（不许手写）。
op：concept / parts / frame / motion / readout / selfcheck / check / route（**全只读·零作用域·不出网**）
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "anatomy-作品解剖-蒸馏.md"
OPS = ("concept", "parts", "frame", "motion", "readout", "selfcheck", "check", "route")


def concept(idea: str = "") -> dict:
    i = (idea or "").strip()
    if not i:
        return {"ok": False, "reason": "need_idea", "how": "给一个要讲解的概念/能力；我找一个**其工作方式就是这个概念**的实物"}
    return {"ok": True, "op": "concept", "kind": "showcase_ops", "idea": i,
            "rule": "**讲概念不是画插图，是造一个真会动的实物**：它的工作过程本身就是这个概念",
            "examples": [
                {"概念": "缓存键（没变就跳过）", "实物": "弹子锁：所有弹子对上才转"},
                {"概念": "一个 GPU 上下文服务多画布", "实物": "龙门绘图仪：单打印头巡 16 个孔位"},
                {"概念": "护栏/授权门", "实物": "闸门 + 钥匙孔：只有主人钥匙能开"},
            ],
            "judges": ["实物的工作过程能一句话对上概念", "不用比喻堆砌，要能**动起来**"],
            "source": "wheresryan22/anatomy（MIT · 只蒸思路与架构）", "doc": str(DOC)}


def parts() -> dict:
    return {"ok": True, "op": "parts", "kind": "showcase_ops",
            "rule": "**几十个小而精确的零件**，每件小而专：有名字 · 有职责 · 有阈值/行程",
            "layers": ["结构层（SVG：外形与装配）", "材质层（着色/渐变/阴影）", "动态层（WebGL 着色器或 3D）"],
            "judges": ["每个零件能指回它在概念里的职责", "零件数够细（不是三块大方块）",
                       "关节/配合关系明确（谁带谁动）"]}


def frame() -> dict:
    return {"ok": True, "op": "frame", "kind": "showcase_ops",
            "parts": ["标题（讲什么）", "一句话提示（怎么看）", "**实时读数**（此刻的状态）", "署名（我们的钢印）"],
            "rule": "画框是**证据框**：读者不用问就能知道这是什么、现在什么状态、谁做的",
            "judges": ["标题/提示/读数/署名四件齐", "读数是**活的**（随运动变化）"]}


def motion() -> dict:
    return {"ok": True, "op": "motion", "kind": "showcase_ops",
            "rule": "**平静地动**：指针悬停/键盘驱动，幅度克制、循环稳态；不炫技、不抖动、不自动播放喧宾夺主",
            "judges": ["无输入时处于稳态", "运动能回到初始位（可反复看）", "帧率与能耗可控"]}


def readout() -> dict:
    return {"ok": True, "op": "readout", "kind": "showcase_ops",
            "rule": "**读数同源**：图里显示的每个数字都必须来自**驱动零件运动的同一个模型/能力位读数**，一个字都不许手写",
            "how": ["模型算出 → 同一份数据既驱动零件位置，也渲染读数",
                    "取不到就读不到（显示未读到），不许填占位数字",
                    "读数带时间戳或版本（可核）"],
            "judges": ["每个数字能指回模型字段或能力位读数（给来源）", "无手写常量当读数", "取不到即如实显示"]}


def selfcheck() -> dict:
    return {"ok": True, "op": "selfcheck", "kind": "showcase_ops",
            "rule": "**放大每个关节自检**：逐零件/逐接缝核对外形与运动，发现错位当场修",
            "steps": ["渲染一张放大图", "逐关节核对（间隙/遮挡/连线）", "逐读数核对（与模型一致）", "记录自检结果"],
            "judges": ["自检记录留痕", "发现的问题与修法成对出现"]}


def check() -> dict:
    return {"ok": True, "op": "check", "kind": "showcase_ops",
            "rules": ["MIT ⇒ 只蒸思路与架构，不搬代码", "**四件齐**（标题/提示/读数/署名）",
                      "**读数同源**（每个数字可指回）", "**自检留痕**（逐关节）",
                      "平静运动 · 未验标未验 · 本 op 集全只读（真出图走 comfy_native / render / figma 等既有位）"],
            "doc": str(DOC)}


def route(idea: str = "") -> dict:
    return {"ok": True, "op": "route", "kind": "showcase_ops", "idea": (idea or "").strip(),
            "map": [{"要什么": "把概念变成会动的实物", "走": "cap showcase_ops op=concept"},
                    {"要什么": "零件分解", "走": "cap showcase_ops op=parts"},
                    {"要什么": "展示框四件", "走": "cap showcase_ops op=frame"},
                    {"要什么": "运动克制", "走": "cap showcase_ops op=motion"},
                    {"要什么": "读数同源", "走": "cap showcase_ops op=readout"},
                    {"要什么": "逐关节自检", "走": "cap showcase_ops op=selfcheck"},
                    {"要什么": "真出图/出片", "走": "comfy_native run / render_evolution / a1art_skill / GenOffice"}],
            "direct": True}


def run(op: str = "concept", **kw) -> dict:
    o = (op or "concept").strip().lower()
    if o == "concept":
        return concept(kw.get("idea") or "")
    if o == "parts":
        return parts()
    if o == "frame":
        return frame()
    if o == "motion":
        return motion()
    if o == "readout":
        return readout()
    if o == "selfcheck":
        return selfcheck()
    if o == "check":
        return check()
    if o == "route":
        return route(kw.get("idea") or "")
    return {"ok": False, "reason": "unknown_op", "op": o, "known": list(OPS)}
