# gbt-capability: director_mood
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""导演 AI 情绪内核（director_mood）· R-H172。

一句命门：**导演自己要有七情六欲，才能投入；不懂人情世故的无奈，就拍不出人味。**

三条公理
  D1 导演有七情六欲，但**情绪只影响"怎么看"，不影响"看到什么"**；
  D2 导演懂人情世故的无奈 —— 呈现时**保留灰度**，不替任何人下结论；
  D3 导演的投入必须**可观测** —— 不许假装懂。

四条红线（写死；每条都有 `tests/test_director_mood.py` 里的带牙用例守着）
  1. **情绪不改数据**：`apply_lens()` 只读输入、返回**新对象**，原数据逐字节不变；
  2. **状态必须可查**：`status()` 必须给出 emotion / drive / intensity / since / trigger；
  3. **情绪有半衰期**：按半衰期衰减，低于阈值**自动退回平静**（不许常驻）；
  4. **导演仍是只读**：本模块**不写任何文件、不碰 store、不产生任何执行授权**。

诚实边界（照实说）
  · 情绪状态是**进程内**状态（会自己衰减），**不是长期档案**；进程重启即回到"平静" —— 这是设计，不是缺陷。
  · 本模块只给"镜头"，**不给结论**：它说不出"这条红不重要"，它只能说"我用什么色调看它"。
"""
from __future__ import annotations

import time

EMOTIONS = ("喜", "怒", "哀", "惧", "爱", "恶", "欲")
CALM = "平静"

# 六欲＝驱动方向（不是情绪，是"往哪使劲"）
DRIVES = {
    "生": "保住存续",
    "繁": "推进",
    "闻": "看见真相",
    "言": "如实呈现",
    "触": "感知改动",
    "息": "知道收手",
}

# 镜头表：情绪影响**怎么看**（呈现），从不影响**看到什么**（事实）。
#   affect = 这份情绪会往哪儿加戏；never = 它**绝对不许**做的越界动作。
LENSES = {
    "喜": {"affect": "呈现时多标一处亮点",
           "never": "不许把『待认领』写成『已完成』"},
    "怒": {"affect": "更突出违规项",
           "never": "不许放大严重程度"},
    "哀": {"affect": "保留灰度，不急着下结论",
           "never": "不许隐去真实红点"},
    "惧": {"affect": "对风险项加一句『可能更糟』的前瞻",
           "never": "不许把推测写成读数"},
    "爱": {"affect": "多给一处上下文，让改动被理解",
           "never": "不许替谁洗白"},
    "恶": {"affect": "对反复踩的坑标注来源",
           "never": "不许针对人，只针对坑"},
    "欲": {"affect": "更强调『下一步能做什么』",
           "never": "不许把愿望写成进度"},
    CALM: {"affect": "不额外着色，照读数呈现",
           "never": "平静不等于没立场：该报的红照报"},
}

DEFAULT_HALF_LIFE_S = 1800.0     # 默认半衰期 30 分钟
FADE_BELOW = 0.05                # 强度低于此值 ⇒ 自动退回"平静"


def _clamp01(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        v = 0.0
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


class DirectorMood:
    """单人情绪状态机：七情 + 六欲 + 强度 + 半衰期。**只读运行，不写任何东西。**"""

    def __init__(self, clock=None):
        self._clock = clock or time.time
        self.reset()

    def _now(self, now=None) -> float:
        return float(self._clock() if now is None else now)

    def reset(self) -> dict:
        """回到"平静"（不是"没有情绪"，是**当下不额外着色**）。"""
        self.emotion = CALM
        self.drive = ""
        self.intensity = 0.0
        self.since = None
        self.trigger = ""
        self.half_life_s = DEFAULT_HALF_LIFE_S
        return self.status()

    def _view(self, at: float):
        """按半衰期算**此刻**还剩多少（不写状态）：返回 (情绪, 强度)。"""
        if self.emotion == CALM or self.since is None:
            return CALM, 0.0
        hl = float(self.half_life_s) if self.half_life_s else DEFAULT_HALF_LIFE_S
        hl = max(1e-6, hl)
        val = float(self.intensity) * (0.5 ** ((at - float(self.since)) / hl))
        if val < FADE_BELOW:
            return CALM, 0.0
        return self.emotion, val

    def _payload(self, emotion: str, intensity: float, at: float, faded_from=None) -> dict:
        age = None if self.since is None else round(at - float(self.since), 3)
        lens = dict(LENSES.get(emotion, LENSES[CALM]))
        out = {
            "ok": True,
            "emotion": emotion,
            "drive": (self.drive if emotion != CALM else ""),
            "drive_meaning": DRIVES.get(self.drive, "") if emotion != CALM else "",
            "intensity": round(float(intensity), 4),
            "since": self.since,
            "trigger": (self.trigger if emotion != CALM else ""),
            "half_life_s": self.half_life_s,
            "age_s": age,
            "calm": emotion == CALM,
            "lens": lens,
            "readonly": True,
        }
        if faded_from:
            out["faded_from"] = faded_from
            out["note"] = "情绪已按半衰期淡出，自动回到平静（情绪有半衰期，不许常驻）"
        return out

    def feel(self, emotion, drive="闻", intensity=0.6, trigger="",
             half_life_s=None, now=None) -> dict:
        """进入一种情绪（七情之一）。非法情绪**直接拒绝**，不许含糊其辞。"""
        if emotion not in EMOTIONS:
            raise ValueError("未知情绪 %r（七情：%s）" % (emotion, "/".join(EMOTIONS)))
        if drive and drive not in DRIVES:
            raise ValueError("未知驱动 %r（六欲：%s）" % (drive, "/".join(DRIVES)))
        at = self._now(now)
        self.emotion = emotion
        self.drive = drive or ""
        self.intensity = _clamp01(intensity)
        self.since = at
        self.trigger = str(trigger or "")[:200]
        if half_life_s:
            self.half_life_s = float(half_life_s)
        return self._payload(emotion, self.intensity, at)

    def decay(self, now=None) -> dict:
        """让情绪按半衰期衰减；淡到阈值以下就**退回平静**（红线 3）。"""
        at = self._now(now)
        emo, val = self._view(at)
        if emo == CALM and self.emotion != CALM:
            faded_from = self.emotion
            keep_hl, keep_drive = self.half_life_s, self.drive
            self.reset()
            self.half_life_s, self.drive = keep_hl, keep_drive
            return self._payload(CALM, 0.0, at, faded_from=faded_from)
        self.intensity = val
        # 抗「二次衰减」：强度写回后，基准时间必须一起挪到此刻 ——
        # 否则下一次 status(now=同一刻) 会**再衰减一遍**（衰减速度超过半衰期）。
        # 这一条是测试当场抓出来的：0.2 被算成 0.1。
        if self.since is not None:
            self.since = at
        return self._payload(emo, val, at)

    def status(self, now=None) -> dict:
        """状态必须可查（红线 2）：不许假装懂，必须留状态。"""
        at = self._now(now)
        emo, val = self._view(at)
        if emo == CALM and self.emotion != CALM:
            return self._payload(CALM, 0.0, at, faded_from=self.emotion)
        return self._payload(emo, val, at)

    def lens(self, now=None) -> dict:
        """当前镜头：**影响怎么看**的那一份说明（含"绝不许做什么"）。"""
        st = self.status(now=now)
        return {"ok": True, **st["lens"], "emotion": st["emotion"],
                "intensity": st["intensity"], "readonly": True}


_DEFAULT = DirectorMood()


def current() -> DirectorMood:
    return _DEFAULT


def apply_lens(rows, mood=None) -> list:
    """把镜头贴到**呈现层**：返回**新列表**（浅拷贝 + `_lens` 字段）。

    红线 1 的机械保证：原列表、原字典**一个字都不动** —— 情绪只能决定怎么摆，
    不能决定事实是什么。（用例会逐字节对比调用前后的原数据。）
    """
    st = (mood or _DEFAULT).status()
    lens = dict(st["lens"])
    lens["emotion"] = st["emotion"]
    lens["intensity"] = st["intensity"]
    out = []
    for row in (rows or []):
        if isinstance(row, dict):
            item = dict(row)                 # 浅拷贝：不写原对象
            item["_lens"] = dict(lens)
            out.append(item)
        else:
            out.append({"_lens": dict(lens), "value": row})
    return out


def feel(emotion, **kw) -> dict:
    return _DEFAULT.feel(emotion, **kw)


def decay(**kw) -> dict:
    return _DEFAULT.decay(**kw)


def status(**kw) -> dict:
    return _DEFAULT.status(**kw)


def lens(**kw) -> dict:
    return _DEFAULT.lens(**kw)


def reset() -> dict:
    return _DEFAULT.reset()


_OPS = {"status": status, "feel": feel, "decay": decay, "lens": lens, "reset": reset}
_FEEL_KEYS = ("drive", "intensity", "trigger", "half_life_s", "now")


def run(op="status", **params) -> dict:
    """能力入口（只读）：status / feel / decay / lens / reset。**不写盘、不执行。**"""
    op = str(op or "status")
    if op == "apply_lens":
        return {"ok": True, "readonly": True, "rows": apply_lens(params.get("rows") or [],
                                                                params.get("mood"))}
    fn = _OPS.get(op)
    if fn is None:
        raise ValueError("未知 op %r（可用：%s）" % (op, "/".join(sorted(_OPS))))
    if op == "feel":
        if not params.get("emotion"):
            raise ValueError("feel 需要 emotion（七情：%s）" % "/".join(EMOTIONS))
        return fn(params["emotion"], **{k: v for k, v in params.items() if k in _FEEL_KEYS})
    keep = {k: v for k, v in params.items() if k == "now"}
    return fn(**keep)


HONEST_BOUNDARY = (
    "情绪内核只保证『情绪是可观测的、有半衰期的、且不改变事实的』。"
    "它不保证『导演的呈现一定合适』—— 合适与否由人看画面来判。"
)
