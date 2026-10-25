# -*- coding: utf-8 -*-
# GBT小土豆V8 永久钢印 · 开发者：自由的风 · 守护者：公主土豆
"""shot_director —— 镜头导演（主人令 2026-10-16：把 Seedance 2.0 Skill OS 蒸进来）

蒸自 Emily2040/seedance-2.0（MIT · v6.7.0）的思想，不搬代码：
  视频模型 = 一个从没见过你的剧组：不能提问 · 按字面渲染 · 只做第一个动作 ·
  跨镜头忘记光位站位 · 不告诉它就不移镜。
十大坑 → 十修法：字面但不死板（感觉 + 一个物理锚）· 一镜一动作 · 道具写手 ·
每镜锁定句（光/人/站位）· 位置与地理每镜重述 · 镜头表先于散文 · 提交前合规预筛。
op：plan / shot_table / rules / punctuation / moderation / evidence / check / route
（全只读 · 零作用域 · 不出网）
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "Seedance2-SkillOS-蒸馏.md"
OPS = ("plan", "shot_table", "rules", "punctuation", "moderation", "evidence", "check", "route")
GATE = "five-dim.py cap shot_director"

RULES = [
    "字面，但绝不死板：写相机会记录的东西；习语按字面渲染 ⇒ 改写成感觉的一个普通词 + 一个物理锚（他愣住，惊慌，眼睛盯着门口的她，喉结动了一下）。",
    "一镜一动作：多动作只做第一个 ⇒ 每镜只给一个动作，别人照常生活（idle business）；但不许写保持不动（会冻成人体模型）。",
    "反应 = 感觉 + 一个物理锚；不是肌肉清单（嘴角压下会读成生闷气）。",
    "道具工作写一只手的动作（否则茶杯会被当酒瓶倒空）。",
    "每镜收尾写锁定句：复述光 · 人 · 站位（否则暖光两镜后变蓝、她已离开门口还在门口说话）。",
    "位置每镜重述；地理每镜重述（否则主客门关系反、反应看向镜头）。",
    "走动必须写出来（否则下一镜她瞬移到杯边）。",
    "结尾必须落在本镜真实存在的构图里（为不存在的构图写的结尾永远不到）。",
    "镜头表（shot table）先于任何散文：表格存在，散文只是它的展开。",
    "多镜/多人 ⇒ 加多镜语法；提交前过合规预筛（分类器拒的是词，不是意图）。",
]
TRAP2FIX = {
    "脸沉下来": "愣住，惊慌，眼睛盯着门口的她，喉结动了一下",
    "脸色难看": "被当场问住，礼貌的笑收住了，他咽了一下",
    "目光如刀": "平静、近乎好笑，她沿货架看过去",
    "心里一紧": "停住半拍，手指在杯沿扣了一下",
    "his face fell": "embarrassed, the polite smile fades and he swallows",
    "a look that could cut": "calm, almost amused, she looks along the shelves",
}


def plan(idea: str = "") -> dict:
    i = (idea or "").strip()
    if not i:
        return {"ok": False, "reason": "need_idea", "how": "给一句想法，例：宴会上她被当众问住"}
    return {"ok": True, "op": "plan", "kind": "shot_director", "idea": i,
            "steps": [
                {"n": 1, "what": "先写镜头表", "judge": "表在散文之前，每镜一格"},
                {"n": 2, "what": "逐镜填格", "judge": "一镜一动作 · 反应=感觉+物理锚 · 道具写手 · 锁行（光/人/站位）"},
                {"n": 3, "what": "多镜/多人加语法", "judge": "位置与地理每镜重述，走动写出来"},
                {"n": 4, "what": "合规预筛", "judge": "分类器拒的是词不是意图 ⇒ 提交前先筛"},
                {"n": 5, "what": "出导演过的提示词", "judge": "结尾落在本镜真实存在的构图里"},
            ],
            "doc": str(DOC), "source_repo": "Emily2040/seedance-2.0（MIT，只蒸思想）"}


def shot_table() -> dict:
    return {"ok": True, "op": "shot_table", "kind": "shot_director",
            "columns": ["镜号", "时长", "一个动作（只写一个）", "反应（感觉 + 一个物理锚）",
                        "道具（一只手在做什么）", "光", "人（谁在场、朝向）", "站位", "锁定句（收尾复述光/人/站位）"],
            "rule": "镜头表先于任何散文；表里每一格都必须是相机会记录的东西"}


def rules() -> dict:
    return {"ok": True, "op": "rules", "kind": "shot_director", "count": len(RULES), "rules": RULES,
            "note": "十条修法全部来自对方三次实拍同场景的十处故障（我们未复现，如实标）"}


def punctuation() -> dict:
    return {"ok": True, "op": "punctuation", "kind": "shot_director", "trap_to_fix": TRAP2FIX,
            "rule": "习语与比喻要么被字面渲染、要么被忽略；一律改写成感觉词 + 一个物理锚"}


def moderation() -> dict:
    return {"ok": True, "op": "moderation", "kind": "shot_director",
            "principle": "分类器拒的是词，不是意图",
            "how": ["提交前先过合规预筛", "把意图翻成中性、字面的词", "不靠回避词、不绕分类器",
                    "被拒就如实报被拒，不换通道硬闯"]}


def evidence() -> dict:
    return {"ok": True, "op": "evidence", "kind": "shot_director",
            "standard": "每条规则都要能指回哪次实拍的哪处故障；指不回就标未验",
            "their_evidence": "三拍同场景（2026-09-26/27）共十处故障 ⇒ 十条规则",
            "our_status": "已蒸入语料与判据；我们未复现其拍摄数据"}


def check() -> dict:
    return {"ok": True, "op": "check", "kind": "shot_director",
            "rules": ["MIT ⇒ 只蒸思想不搬代码", "不代付生成费（生成与费用归视频提供方）",
                      "不编证据（指不回故障的规则标未验）", "合规走预筛，不绕分类器",
                      "落点只走我们自己的目录"],
            "doc": str(DOC)}


def route(idea: str = "") -> dict:
    return {"ok": True, "op": "route", "kind": "shot_director", "idea": (idea or "").strip(),
            "path": ["一句想法", GATE, "镜头表", "逐镜提示词", "合规预筛", "提交给视频提供方"],
            "direct": True}


def run(op: str = "plan", **kw) -> dict:
    o = (op or "plan").strip().lower()
    if o == "plan":
        return plan(kw.get("idea") or "")
    if o == "shot_table":
        return shot_table()
    if o == "rules":
        return rules()
    if o == "punctuation":
        return punctuation()
    if o == "moderation":
        return moderation()
    if o == "evidence":
        return evidence()
    if o == "check":
        return check()
    if o == "route":
        return route(kw.get("idea") or "")
    return {"ok": False, "reason": "unknown_op", "op": o, "known": list(OPS)}
