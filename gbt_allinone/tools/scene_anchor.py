# gbt-capability: scene_anchor
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""场景锚定系统（scene_anchor）· R-H185 只读骨架。

**作品不是为情绪做的，是为场景做的。**
钩子必须钩住**触发场景**——场景不是背景，是钩子的真正落点。

三层：场景分类（8 大类）· 灵魂锚定（四要素）· 钩子匹配（锚场景不锚情绪）。

四条红线（做成机械闸）：
  ① 先找场景再做作品：四要素缺任一 ⇒ 拒绝；
  ② 场景必须具体：只填类别词 ⇒ 拒绝（"失恋"是类别，"分手后第 37 天翻到旧照片"才是场景）；
  ③ 钩子锚场景不锚情绪：纯情绪/夸张词或没有场景标记 ⇒ 拒绝；
  ④ 灵魂必须能被说清：`soul()` 四要素齐全才算有魂。

本模块只读：不写盘、不出网、不生成任何作品。
"""
from __future__ import annotations

# 8 大类场景（骨架）：细分场景按作品逐步填，**不假装有真实数据**
SCENE_CLASSES = {
    "失去": {"scenes": ("失恋", "亲人离世", "朋友走散", "梦想破碎"),
             "emotions": ("伤感", "哀", "无助")},
    "重逢": {"scenes": ("老友相聚", "久别重逢", "破镜重圆"),
             "emotions": ("喜", "爱", "温暖")},
    "挣扎": {"scenes": ("加班深夜", "备考", "创业", "复读"),
             "emotions": ("疲惫", "不甘", "倔强")},
    "突破": {"scenes": ("毕业", "拿到 offer", "第一次登台", "手术成功"),
             "emotions": ("喜悦", "激动", "感激")},
    "孤独": {"scenes": ("一个人吃饭", "深夜回家", "异地漂泊"),
             "emotions": ("孤独", "想念", "温柔")},
    "愤怒": {"scenes": ("被辜负", "被误解", "被不公对待"),
             "emotions": ("怒", "不甘", "反抗")},
    "治愈": {"scenes": ("撑不下去", "想放弃", "需要有人陪"),
             "emotions": ("疲惫", "渴望", "温柔")},
    "怀旧": {"scenes": ("翻旧照片", "回老家", "听老歌"),
             "emotions": ("想念", "温柔", "感慨")},
}

SOUL_KEYS = ("scene", "emotion_response", "resonance", "blank")
SOUL_CN = {"scene": "触发场景", "emotion_response": "情绪反应",
           "resonance": "共鸣点", "blank": "留白"}

# 场景"具体化"的机械标记：有数字 / 有时间 / 有具体动作，才算"瞬间"而不是"类别"
_SPECIFIC_MARKERS = ("第", "后", "那天", "那晚", "凌晨", "半夜", "深夜", "翻到",
                     "收到", "看到", "走出", "第一次", "最后一次", "的时候", "间")

_ALL_CLASS_WORDS = tuple(SCENE_CLASSES) + tuple(
    s for blk in SCENE_CLASSES.values() for s in blk["scenes"])

_EMOTION_ONLY_HINTS = ("太伤感了", "燃爆了", "治愈系音乐推荐", "快乐歌曲合集",
                       "伤感歌曲合集", "听哭了", "神曲", "合集", "推荐")

MIN_SCENE_CHARS = 10


def classes() -> dict:
    """查 8 大类骨架（只读）。"""
    return {"ok": True, "readonly": True,
            "classes": [{"key": k, "scenes": list(v["scenes"]),
                         "emotions": list(v["emotions"])} for k, v in SCENE_CLASSES.items()],
            "count": len(SCENE_CLASSES),
            "note": "骨架表：细分场景按作品逐步填 —— 不假装有真实场景数据"}


def _scene_is_concrete(scene: str) -> bool:
    """场景够不够具体：长度 + 必须有"具体化标记"（数字/时间/动作）。"""
    s = str(scene or "").strip()
    if len(s) < MIN_SCENE_CHARS:
        return False
    if s in _ALL_CLASS_WORDS or s in SCENE_CLASSES:
        return False
    return any(m in s for m in _SPECIFIC_MARKERS)


def soul(scene: str, emotion_response: str, resonance: str, blank: str) -> dict:
    """灵魂锚定层：四要素缺一不可；场景必须具体（红线 ①②④）。"""
    got = {"scene": str(scene or "").strip(),
           "emotion_response": str(emotion_response or "").strip(),
           "resonance": str(resonance or "").strip(),
           "blank": str(blank or "").strip()}
    missing = [k for k in SOUL_KEYS if not got[k]]
    if missing:
        return {"ok": False, "denied": True, "missing": missing,
                "why": "四要素缺一不可（缺 %s）⇒ 没找到场景不许开工"
                       % "/".join(SOUL_CN[k] for k in missing)}
    if not _scene_is_concrete(got["scene"]):
        return {"ok": False, "denied": True, "rule": "scene_not_concrete",
                "why": "场景必须具体：『%s』是类别，要写到『分手后第 37 天翻到旧照片』这种瞬间"
                       % got["scene"][:30]}
    return {"ok": True, "readonly": True, "soul": got, "elements": list(SOUL_KEYS)}


def hook(text: str, scene: str = "") -> dict:
    """钩子匹配层：**锚场景，不锚情绪**（红线 ③）。"""
    t = str(text or "").strip()
    if not t:
        return {"ok": False, "denied": True, "rule": "empty_hook", "why": "钩子不能为空"}
    hits = [h for h in _EMOTION_ONLY_HINTS if h in t]
    if hits:
        return {"ok": False, "denied": True, "rule": "hook_anchors_emotion",
                "why": "钩子锚了情绪（出现 %s）：要锚场景，如『分手后半夜翻到旧照片的人』" % hits}
    ref = str(scene or t).strip()
    if not _scene_is_concrete(ref):
        return {"ok": False, "denied": True, "rule": "hook_has_no_scene",
                "why": "钩子里没有可辨认的场景（要含时间/数字/具体动作）"}
    return {"ok": True, "readonly": True, "hook": t, "anchored_scene": ref}


def run(op="classes", **params) -> dict:
    """能力入口（只读）：classes / soul / hook / redlines。不写盘、不出网、不生成。"""
    op = str(op or "classes")
    if op == "classes":
        return classes()
    if op == "soul":
        return soul(params.get("scene", ""), params.get("emotion_response", ""),
                    params.get("resonance", ""), params.get("blank", ""))
    if op == "hook":
        return hook(params.get("text", ""), params.get("scene", ""))
    if op == "redlines":
        return {"ok": True, "readonly": True, "classes": list(SCENE_CLASSES),
                "soul_elements": [{"key": k, "cn": SOUL_CN[k]} for k in SOUL_KEYS],
                "red_lines": [
                    "先找场景，再做作品（没找到具体场景不许开工）",
                    "场景必须具体（类别 ≠ 场景）",
                    "钩子锚场景，不锚情绪",
                    "灵魂必须能被说清（四要素缺一不可）",
                ]}
    raise ValueError("未知 op %r（可用：classes/soul/hook/redlines）" % (op,))


HONEST_BOUNDARY = (
    "本骨架只保证『场景够具体、四要素齐、钩子锚的是场景』。"
    "『这个场景够不够打动人』只有人知道 —— 机器判不了共鸣。"
)
