# gbt-capability: emotion_projection
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""情感投射系统（emotion_projection）· R-H183 只读骨架。

**作品最大的价值，不是"好听"，是"听了之后觉得那是在说自己"。**

三层：叙事层（生成前四问）· 投射层（生成中五元素的细节动作）· 校验层（生成后四项）。

四条红线（做成机械闸）：
  ① 不演情绪真投入：四个问题缺任一 ⇒ 拒绝；
  ② 不套模板：出现纯情绪/参数标签（我好难过、悲伤的旋律、钢琴+弦乐、快节奏）⇒ 拒绝；
  ③ 不操纵观众：出现"赚眼泪 / 带节奏 / 贩卖焦虑 / 煽动"类字眼 ⇒ 拒绝；
  ④ **机器能判的归机器，人才能判的归人**：前三项机器判；"是否身临其境"**只有人能判**
     —— 机器设 True 判违规；未判则 pending_human（**不通过**）。

本模块只出**结构校验**：不生成、不落盘、不出网。
"""
from __future__ import annotations

EMOTIONS = ("喜", "怒", "哀", "惧", "爱", "恶", "欲")

# R-H189 · 贯通①：四问里的"听众代入什么"**换成"触发场景是什么"**（场景锚定接管）
QUESTIONS = ("who", "why", "scene", "blank")
QUESTION_CN = {"who": "谁在感受这个情绪", "why": "为什么（来龙去脉，不是标签）",
               "scene": "触发场景是什么（要具体到某个瞬间）", "blank": "留白在哪"}


def _scene_gate() -> tuple:
    """贯通①：场景的具体性判据**引用场景锚定那一份**（唯一真相源，不另抄一份）。"""
    from . import scene_anchor
    return scene_anchor._scene_is_concrete, scene_anchor.SCENE_CLASSES

ELEMENTS = ("melody", "lyric", "arrangement", "vocal", "blank")
ELEMENT_CN = {"melody": "旋律", "lyric": "歌词", "arrangement": "编曲",
              "vocal": "人声", "blank": "留白"}

MACHINE_CHECKS = ("narrative_complete", "emotion_coherent", "no_template")
HUMAN_CHECK = "immersive"

_LABEL_HINTS = ("我好难过", "我好开心", "悲伤的旋律", "快乐的旋律", "钢琴+弦乐",
                "快节奏", "慢歌", "小调", "大调", "悲伤的唱腔", "通用伤感")
_MANIPULATE_HINTS = ("赚眼泪", "带节奏", "贩卖焦虑", "煽动", "割韭菜", "情绪绑架")

# 阈值按元素分开：**主人的例句本身就是短的**（"一个刚分手的人" 7 字、
# "最该说话的时候不说话" 10 字）—— 一刀切会把真叙事误判成标签（用例当场抓出）。
MIN_CHARS = {"who": 4, "why": 8, "empathy": 8, "blank": 8,
             "melody": 8, "lyric": 8, "arrangement": 8, "vocal": 8}
DEFAULT_MIN_CHARS = 8


def _is_label(text: str, key: str = "") -> bool:
    """粗判『标签式』：过短，或只有情绪/参数标签的短句（阈值按元素分）。"""
    s = str(text or "").strip()
    floor = MIN_CHARS.get(key, DEFAULT_MIN_CHARS)
    if len(s) < floor:
        return True
    return any(h in s for h in _LABEL_HINTS) and len(s) < floor * 2


def narrate(who: str, why: str, scene: str, blank: str) -> dict:
    """叙事层（生成前）：四问必须全答，且不许是标签；**触发场景必须具体**（贯通①）。"""
    got = {"who": str(who or "").strip(), "why": str(why or "").strip(),
           "scene": str(scene or "").strip(), "blank": str(blank or "").strip()}
    missing = [k for k in QUESTIONS if not got[k]]
    if missing:
        return {"ok": False, "denied": True, "missing": missing,
                "why": "四问缺任一 ⇒ 拒绝：不演情绪，真投入（缺 %s）"
                       % "/".join(QUESTION_CN[k] for k in missing)}
    bad = [k for k, v in got.items() if _is_label(v, k)]
    if bad:
        return {"ok": False, "denied": True, "label_only": bad,
                "why": "只给标签不算叙事（%s）：要写来龙去脉" % "/".join(bad)}
    concrete, _classes = _scene_gate()
    if not concrete(got["scene"]):
        return {"ok": False, "denied": True, "rule": "scene_not_concrete",
                "why": "触发场景必须具体（贯通场景锚定）：『%s』是类别，要写到某个瞬间"
                       % got["scene"][:30]}
    return {"ok": True, "readonly": True, "narrative": got, "questions": list(QUESTIONS)}


def project(melody: str, lyric: str, arrangement: str, vocal: str, blank: str) -> dict:
    """投射层（生成中）：五个元素都必须是细节动作，不是情绪标签。"""
    got = {"melody": str(melody or "").strip(), "lyric": str(lyric or "").strip(),
           "arrangement": str(arrangement or "").strip(), "vocal": str(vocal or "").strip(),
           "blank": str(blank or "").strip()}
    missing = [k for k in ELEMENTS if not got[k]]
    if missing:
        return {"ok": False, "denied": True, "missing": missing,
                "why": "五元素缺任一 ⇒ 拒绝（缺 %s）"
                       % "/".join(ELEMENT_CN[k] for k in missing)}
    labels = [k for k, v in got.items() if _is_label(v, k)]
    if labels:
        return {"ok": False, "denied": True, "label_only": labels,
                "why": "标签不是投射（%s）：要写『细节动作』（如『副歌前只剩钢琴』）"
                       % "/".join(ELEMENT_CN[k] for k in labels)}
    return {"ok": True, "readonly": True, "projection": got, "elements": list(ELEMENTS)}


def check(narrative: dict | None, projection: dict | None,
          machine: dict | None = None, immersive_by: str = "",
          immersive_value=None) -> dict:
    """校验层（生成后）：机器判前三项；『是否身临其境』只有人能判。"""
    machine = dict(machine or {})
    verdicts = {k: bool(machine.get(k)) for k in MACHINE_CHECKS}
    by = str(immersive_by or "").strip().lower()
    if immersive_value is not None and by != "human":
        return {"ok": False, "denied": True,
                "why": "机器不许替人下『身临其境』的结论（红线 4）：请由人听过后再判"}
    human_done = by == "human" and immersive_value is not None
    all_machine = all(verdicts.values())
    passed = bool(all_machine and human_done and bool(immersive_value))
    return {
        "ok": True,
        "readonly": True,
        "machine_verdicts": verdicts,
        "machine_all_pass": all_machine,
        "immersive": {"by": by or "pending", "value": immersive_value,
                      "pending_human": not human_done},
        "passed": passed,
        "publish": passed,
        "why": ("四项全过 ⇒ 可进发布队列" if passed else
                ("机器三项已过，等**人**听过后判『身临其境』（未判 ⇒ 不通过）"
                 if all_machine else "机器校验未过 ⇒ 打回重做")),
        "note": "校验不过 ⇒ 打回重做，不进入发布队列",
    }


def scan_text(text: str) -> dict:
    """文本红线扫描（只读）：不套模板 / 不操纵观众。"""
    t = str(text or "")
    problems = []
    for h in _LABEL_HINTS:
        if h in t:
            problems.append({"rule": "no_template", "why": "出现标签式表达：%s" % h})
    for h in _MANIPULATE_HINTS:
        if h in t:
            problems.append({"rule": "no_manipulation", "why": "不操纵观众（出现 %s）" % h})
    return {"ok": not problems, "readonly": True, "problems": problems}


def run(op="model", **params) -> dict:
    """能力入口（只读）：model / narrate / project / check / scan。不生成、不落盘、不出网。"""
    op = str(op or "model")
    if op == "model":
        return {"ok": True, "readonly": True, "emotions": list(EMOTIONS),
                "questions": [{"key": k, "cn": QUESTION_CN[k]} for k in QUESTIONS],
                "elements": [{"key": k, "cn": ELEMENT_CN[k]} for k in ELEMENTS],
                "machine_checks": list(MACHINE_CHECKS), "human_check": HUMAN_CHECK,
                "note": "机器能判的归机器，人才能判的归人"}
    if op == "narrate":
        return narrate(params.get("who", ""), params.get("why", ""),
                       params.get("scene", ""), params.get("blank", ""))
    if op == "project":
        return project(params.get("melody", ""), params.get("lyric", ""),
                       params.get("arrangement", ""), params.get("vocal", ""),
                       params.get("blank", ""))
    if op == "check":
        return check(params.get("narrative"), params.get("projection"),
                     params.get("machine"), params.get("immersive_by", ""),
                     params.get("immersive_value"))
    if op == "scan":
        return scan_text(params.get("text", ""))
    if op == "scene_classes":
        # 贯通①的可见面：情感投射这边能直接查"场景锚定的 8 大类"（真引用那一份）
        from . import scene_anchor
        return {"ok": True, "readonly": True, "from": "tool.scene_anchor",
                "classes": list(scene_anchor.SCENE_CLASSES)}
    raise ValueError("未知 op %r（可用：model/narrate/project/check/scan/scene_classes）" % (op,))


HONEST_BOUNDARY = (
    "本模块只保证『叙事结构完整、情绪连贯、不套模板』。"
    "『是否真的让人身临其境』只有人听了才知道 —— 这条不假装能自动化。"
)
