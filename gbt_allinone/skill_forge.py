# -*- coding: utf-8 -*-
# GBT小土豆V8 永久钢印 · 开发者：自由的风 · 守护者：公主土豆
"""skill_forge —— 技能蒸馏五式（主人令 2026-10-16：把五个 skill 蒸成我们的原生能力）

蒸自五个 MIT 仓的**思想**，不搬代码：
  ① 女娲.skill（alchaincyf/nuwa-skill）：**不是复制人，是提炼思维框架** —— 心智模型/决策启发式/表达DNA/边界
  ② last30days（mvanhorn/last30days-skill）：**agent 主导的搜索，按投票与真实金额计分**，跨 Reddit/X/YouTube/HN/Polymarket/web
  ③ 同事.skill（titanwings/distilly）：把**离职同事的聊天记录与经验**蒸成可复用技能
  ④ 前任.skill（therealXiaomanChu/ex-skill）：**原材料（聊天/朋友圈/照片）+ 主观描述** → 说话方式 DNA
  ⑤ 反蒸馏.skill（leilei926524-tech/anti-distill）：交出版**消毒**（看着完整专业）+ **私有备份**留核心
op：think / radar / experience / style / anti / check / route（**全只读·零作用域·不出网**）
边界：MIT 只蒸思想；**隐私**——原材料只在本人设备、不外发、不泄露第三方；**不搬代码**；落只走我们自己的目录。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "技能蒸馏五式-蒸馏.md"
OPS = ("think", "radar", "experience", "style", "anti", "check", "route")


def think(subject: str = "") -> dict:
    s = (subject or "").strip()
    if not s:
        return {"ok": False, "reason": "need_subject",
                "how": "给一个对象（人名/主题）或一句模糊需求；模糊需求先诊断再蒸馏"}
    return {"ok": True, "op": "think", "kind": "skill_forge", "subject": s,
            "core": "**不是复制人，是提炼思维框架**（一套可运行的认知操作系统）",
            "axes": [
                {"轴": "心智模型（镜片）", "问": "他用什么模型看世界？", "判据": "每个模型能指回一处出处"},
                {"轴": "决策启发式（直觉规则）", "问": "他在什么情形下选哪条？", "判据": "写成 if 情形 then 规则"},
                {"轴": "表达 DNA", "问": "他怎么说话？", "判据": "给 3 条可复现的句式特征"},
                {"轴": "边界（绝不会）", "问": "他绝不做什么？", "判据": "至少 3 条否决项"},
            ],
            "two_entries": ["明确对象 ⇒ 直接蒸馏", "模糊需求 ⇒ 先诊断推荐 ⇒ 再蒸馏"],
            "source": "alchaincyf/nuwa-skill（MIT，只蒸思想）", "doc": str(DOC)}


def radar(topic: str = "") -> dict:
    t = (topic or "").strip()
    return {"ok": True, "op": "radar", "kind": "skill_forge", "topic": t or "（未给主题）",
            "principle": "**agent 主导的搜索**：按社区投票与真实金额计分，**不是编辑评分**",
            "platforms": ["Reddit", "X", "YouTube", "HackerNews", "Polymarket", "web"],
            "pipeline": ["起主题词与同义词", "分平台取原始讨论", "去重与按分数排序",
                         "交叉印证（≥2 平台一致才升级为结论）", "出**有据总结**（每条带出处）"],
            "judges": ["每条结论能指回原始贴与其分数", "单平台孤证只能标「未交叉验证」",
                       "取不到就读不到，不编热度"],
            "needs": "各平台凭据/网关如实报（已配/未配）；不在位就只出计划不出数据",
            "source": "mvanhorn/last30days-skill（MIT，只蒸思想）"}


def experience(material: str = "") -> dict:
    m = (material or "").strip()
    return {"ok": True, "op": "experience", "kind": "skill_forge", "material": m or "（未给原材料）",
            "steps": ["切主题（谁/在什么场景/怎么解决）", "抽可复用规则（if 情形 then 做法）",
                      "抽反模式（踩过的坑）", "写成技能包（名称/用途/步骤/判据/坑）", "入索引并留出处"],
            "judges": ["每条规则能指回原对话或文档", "**他人隐私一律脱敏**（人名/联系方式/私事）",
                       "只留可复用，不留八卦"],
            "boundary": "与 book_skill 分工：书/文档 → book_skill；**人的经验/对话 → 本 op**",
            "source": "titanwings/distilly（MIT，只蒸思想）"}


def style(material: str = "") -> dict:
    m = (material or "").strip()
    return {"ok": True, "op": "style", "kind": "skill_forge", "material": m or "（未给原材料）",
            "inputs": ["聊天记录", "朋友圈/动态", "照片（仅元数据与场景，不做人脸建模）", "本人主观描述"],
            "outputs": ["用词习惯", "句子长度与标点节奏", "口头禅与口头语气", "情绪触发点", "**不说什么**（边界）"],
            "privacy_gate": ["原材料**只在本人设备**处理，不上传、不外发",
                             "涉及第三方的内容一律脱敏",
                             "不做人脸/声纹建模（超出必要）", "产物只落我们自己的目录"],
            "judges": ["风格特征可复核（每条给 2 个例子）", "不冒充真人身份发消息（明示为风格模拟）"],
            "source": "therealXiaomanChu/ex-skill（MIT，只蒸思想）"}


def anti(asset: str = "") -> dict:
    a = (asset or "").strip()
    return {"ok": True, "op": "anti", "kind": "skill_forge", "asset": a or "（未给资产）",
            "two_versions": {"交出版": "**看着完整专业**（可交接、可交付）",
                             "私有备份": "**把有价值的部分从公开版移除后留下的核心**（自己真正的资产）"},
            "steps": ["先定「交付契约」（对方要什么）", "再定「核心清单」（自己必须留什么）",
                      "生成交出版（自洽、可跑、无空洞占位）", "生成私有备份（核心 + 来源 + 时间戳）",
                      "两版互查：交出版不泄核心，私有备份不丢关键"],
            "ethics": "**用于保护个人核心知识与合规留存**；不用于欺骗、不伪造履历、不破坏对方系统",
            "judges": ["交出版可被独立复跑", "私有备份含核心且**不外发**（落本地并登记）"],
            "source": "leilei926524-tech/anti-distill（MIT，只蒸思想）"}


def check() -> dict:
    return {"ok": True, "op": "check", "kind": "skill_forge",
            "rules": ["五个来源全是 MIT ⇒ **只蒸思想不搬代码**",
                      "**隐私红线**：原材料不外发、第三方脱敏、不做人脸/声纹建模",
                      "**不冒充真人**：风格复刻必须明示为模拟",
                      "反蒸馏只用于保护自己的知识，不用于欺骗",
                      "落点只走我们自己的目录", "取不到就读不到，不编热度/结论"],
            "doc": str(DOC)}


def route(subject: str = "") -> dict:
    return {"ok": True, "op": "route", "kind": "skill_forge", "subject": (subject or "").strip(),
            "map": [{"要什么": "借某人的思维", "走": "cap skill_forge think"},
                    {"要什么": "全网活人讨论", "走": "cap skill_forge radar"},
                    {"要什么": "把经验变技能", "走": "cap skill_forge experience"},
                    {"要什么": "复刻说话方式", "走": "cap skill_forge style"},
                    {"要什么": "交差但留核心", "走": "cap skill_forge anti"}],
            "direct": True}


def run(op: str = "think", **kw) -> dict:
    o = (op or "think").strip().lower()
    if o == "think":
        return think(kw.get("subject") or "")
    if o == "radar":
        return radar(kw.get("topic") or "")
    if o == "experience":
        return experience(kw.get("material") or "")
    if o == "style":
        return style(kw.get("material") or "")
    if o == "anti":
        return anti(kw.get("asset") or "")
    if o == "check":
        return check()
    if o == "route":
        return route(kw.get("subject") or "")
    return {"ok": False, "reason": "unknown_op", "op": o, "known": list(OPS)}
