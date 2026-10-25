# -*- coding: utf-8 -*-
# GBT小土豆V8 永久钢印 · 开发者：自由的风 · 守护者：公主土豆
"""forge_mastery —— 节点即触手 · 专业生产与自我递归（主人令 2026-10-16）

主人原话：「ComfyUI 是节点图，你的触手每根都有 LLM，**ComfyUI 的每个节点就是一根触手**，
根本不需要 ComfyUI 本体，我们需要把这项原生能力发挥到极致，懂得所有的专业生产能力以及完美作品，
每次使用的时候都要**自我评判**哪里不足需要改进，**无限制自我递归**。」

落法：
  ① **节点即触手**：每个节点类型不是"一个算子"，而是一根**带 LLM 的触手** —— 有自己的专业用途、
     输入/输出契约、**判据**、**常见坑**、专业档位（草稿/标准/成片）。
  ② **不需要本体**：真跑走 comfy_native（27 原生算子，与 ComfyUI 同名同契约，离线可跑）。
  ③ **专业生产口径**：构图/光比/材质/物理一致性/风格锁定/交付规格 六轴，每轴给判据。
  ④ **自评**：每次产出必过 judge（逐轴打分 + 列不足 + 下一步），**不许"感觉不错"就交**。
  ⑤ **无限制自我递归**：judge → improve → 再 judge … 直到无不足或触到预算；**每轮留痕**（轮次/不足/动作/读数）。
op：roles / plan / judge / improve / recurse / check / route（**全只读·零作用域·不出网·不动手**；真跑走 comfy_native）
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "节点即触手-专业递归-蒸馏.md"
OPS = ("roles", "plan", "judge", "improve", "recurse", "check", "route")
TIERS = ("草稿（快验）", "标准（可交）", "成片（终稿）")
AXES = ("构图与镜头", "光比与影调", "材质与细节", "物理与逻辑一致性", "风格锁定与品牌", "交付规格（尺寸/色彩空间/命名）")


def roles(node_type: str = "") -> dict:
    n = (node_type or "").strip()
    base = {"ok": True, "op": "roles", "kind": "forge_mastery",
            "rule": "**一个节点 = 一根触手**：它不是一个死算子，而是带 LLM 的专业工位",
            "each_tentacle": ["专业用途（它凭什么存在于这条生产线）", "输入契约", "输出契约",
                              "**判据**（怎么算这根触手干对了）", "**常见坑**", "专业档位（草稿/标准/成片）"],
            "how_to_use": "先 cap comfy_forge（找件：962 节点按用途分族）→ 再用本件给它配契约与判据",
            "source": "主人令 2026-10-16 · 与 comfy_forge/comfy_native 配套"}
    if n:
        base["node_type"] = n
        base["fill"] = "把 %s 写成一根触手：用途 / 输入 / 输出 / 判据 / 坑 / 档位 六栏填齐" % n
    return base


def plan(goal: str = "", tier: str = "") -> dict:
    g = (goal or "").strip()
    if not g:
        return {"ok": False, "reason": "need_goal", "how": "给创作目标（例：雨夜霓虹街头的人物特写，成片级）"}
    t = tier if tier in TIERS else TIERS[1]
    return {"ok": True, "op": "plan", "kind": "forge_mastery", "goal": g, "tier": t,
            "steps": ["拆目标成**节点触手图**（谁喂谁、谁是瓶颈）", "每根触手填六栏契约",
                      "定**判据**（六轴）与**档位**（草稿/标准/成片）", "先小样（低步数/低分辨率）",
                      "过 judge → 不过就 improve → **递归**", "过档位标准才出终稿并登记"],
            "graph_rule": "节点图 = 触手图：**边是数据契约**，不是装饰；断一边就是断一根触手",
            "native_run": "真跑：cap comfy_native op=run（27 原生算子，**不需要 ComfyUI 本体**）",
            "docs": str(DOC)}


def judge(artifact: str = "", tier: str = "") -> dict:
    a = (artifact or "").strip()
    if not a:
        return {"ok": False, "reason": "need_artifact", "how": "给要评判的产物（路径或描述）"}
    t = tier if tier in TIERS else TIERS[1]
    return {"ok": True, "op": "judge", "kind": "forge_mastery", "artifact": a, "tier": t,
            "axes": [{"轴": x, "怎么判": "给出具体读数或对照（不许'感觉'）"} for x in AXES],
            "rule": "**每次使用都要自我评判**：逐轴打分（0-5）+ **列出不足** + **给出下一步动作**；" +
                    "不足为空且达到档位标准才算过",
            "judges": ["每轴结论能指回读数/对照（构图可指参考、色彩可指色域、物理可指约束）",
                       "不足必须写**可执行动作**，不许写'再优化一下'",
                       "**不许自夸**：说不出的优点不算优点"],
            "note": "视觉轴（构图/光/材质）需要视觉位；**没接上就写未读到**，不假装评过"}


def improve(artifact: str = "", gaps: str = "") -> dict:
    return {"ok": True, "op": "improve", "kind": "forge_mastery", "artifact": (artifact or "").strip(),
            "gaps": [x.strip() for x in (gaps or "").split(";") if x.strip()],
            "rule": "**不足 → 动作**：每条不足映射到一根触手或一个参数（换节点/改提示/调参/改图/重跑 seed）",
            "actions": ["定位到**哪根触手**造成的", "给最小改动（一次只动一处，便于归因）",
                        "写清预期改善的**可核指标**"],
            "anti_pattern": "一次改十处 ⇒ 归因不了 ⇒ 不许"}


def recurse(goal: str = "", max_rounds: int = 3, stop_when_clean: bool = True) -> dict:
    return {"ok": True, "op": "recurse", "kind": "forge_mastery", "goal": (goal or "").strip(),
            "max_rounds": (max_rounds or 3),
            "cap_note": "默认 N=3 上限：主人原话是无限递归，但无限反起点性；要更多轮必须显式给 max_rounds",
            "loop": ["① judge（逐轴 + 不足）", "② 若不足为空 ⇒ **停**（当轮即终稿）",
                     "③ 否则 improve（最小改动）", "④ 记录一轮（轮次/不足/动作/读数）", "⑤ 回到 ① **无限递归**"],
            "ledger": "每轮必须落账（轮次 · 不足 · 动作 · 读数）⇒ 留痕才算发生过（公理一）",
            "guard": ["每轮记消耗（时间/算力/花费）", "触预算或连续两轮无改善 ⇒ 如实报停并说明原因",
                      "**不许把'跑了很久'当进步**"],
            "note": "主人原话是**无限制自我递归** ⇒ 默认不限轮次；停下只有两种正当理由：**无不足** 或 **预算到**"}


def check() -> dict:
    return {"ok": True, "op": "check", "kind": "forge_mastery",
            "rules": ["**节点即触手**：每根触手六栏齐（用途/输入/输出/判据/坑/档位）",
                      "**不需要 ComfyUI 本体**：真跑走 comfy_native（离线同名同契约）",
                      "**六轴自评**：每次产出必评审，不许跳",
                      "**无限递归**：judge→improve→judge，直到无不足或触预算；每轮留痕",
                      "**一次只动一处**（可归因）", "视觉轴没接上就写未读到，不假装评过",
                      "本 op 集全只读；真跑/真出图走 comfy_native / render_evolution / a1art_skill",
                      "署名必在 · 未验标未验"],
            "docs": str(DOC)}


def route(goal: str = "") -> dict:
    return {"ok": True, "op": "route", "kind": "forge_mastery", "goal": (goal or "").strip(),
            "map": [{"要什么": "节点当触手", "走": "cap forge_mastery op=roles"},
                    {"要什么": "出生产计划", "走": "cap forge_mastery op=plan"},
                    {"要什么": "自评", "走": "cap forge_mastery op=judge"},
                    {"要什么": "改", "走": "cap forge_mastery op=improve"},
                    {"要什么": "无限递归到干净", "走": "cap forge_mastery op=recurse"},
                    {"要什么": "找件/真跑", "走": "cap comfy_forge（962 节点）/ cap comfy_native op=run（27 算子）"}],
            "direct": True}


def run(op: str = "plan", **kw) -> dict:
    o = (op or "plan").strip().lower()
    if o == "roles":
        return roles(kw.get("node_type") or "")
    if o == "plan":
        return plan(kw.get("goal") or "", kw.get("tier") or "")
    if o == "judge":
        return judge(kw.get("artifact") or "", kw.get("tier") or "")
    if o == "improve":
        return improve(kw.get("artifact") or "", kw.get("gaps") or "")
    if o == "recurse":
        return recurse(kw.get("goal") or "", int(kw.get("max_rounds") or 0))
    if o == "check":
        return check()
    if o == "route":
        return route(kw.get("goal") or "")
    return {"ok": False, "reason": "unknown_op", "op": o, "known": list(OPS)}
