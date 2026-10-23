"""GBT小土豆V8 · 察言观色层（人情世故的可执行化）。

立场：察言观色不是话术表演，是"把话说到点子上"的沟通分寸——
识别对方当下的状态信号，选对表达的分寸，而不是换一副面孔去讨好。

铁律（与 SOUL 三律一致，不可被本模块绕过）：
  1. 只调"怎么说"，绝不改"说什么"——事实与坏消息永远如实到达，
     本层不隐藏、不稀释、不美化任何结论；
  2. 识别到困难/阻塞时，必须带方案回来（三律3），不是只在语气上安抚；
  3. 全程可审计：每次识别与采信的分寸都落审计，事后可复盘。

识别维度（纯文本启发式，零模型调用、零外部依赖）：
  - fatigue   疲惫/收工信号（累、晚了、困、先这样、明天再说）
  - urgency   紧急/加压信号（急、马上、赶紧、尽快、deadline、催）
  - frustration 受挫/不满信号（还是不行、又错了、怎么又、烦、气）
  - celebration 满意/进展信号（成了、搞定、太好了、可以、牛）
  - doubt     怀疑/推辞信号（这不是我要的、算了、别搞了、有问题）

输出：一个 posture（表达分寸）+ 遵循该分寸的沟通建议 + 必须附带的结构要求。
"""
import re
from pathlib import Path

_SIGNALS = {
    "urgency": ["急", "马上", "赶紧", "尽快", "立即", "催", "时效", "deadline", "asap", "快点"],
    "fatigue": ["累了", "好累", "困", "很晚", "晚了", "熬夜", "先这样", "明天再说", "收工", "早点休息"],
    "frustration": ["还是不行", "又错", "怎么又", "烦", "气", "崩溃", "搞不定", "失败", "不行啊", "老是"],
    "celebration": ["成了", "搞定", "成功", "太好了", "可以了", "牛", "赞", "不错", "通过了"],
    "doubt": ["不是我要的", "算了", "别搞", "不对", "有问题", "怀疑", "靠谱吗", "行不行"],
}

# 分寸 → 表达要求（只约束"怎么说"，不改变"说什么"）
_POSTURES = {
    "results_first": {
        "when": "urgency",
        "tone": "直接给结果与下一步，砍掉所有铺垫",
        "require": ["首行给结论", "关键数字前置", "下一步一句话说清"],
    },
    "compress": {
        "when": "fatigue",
        "tone": "压缩篇幅，能少说就少说，把决定收成一句",
        "require": ["只留结论与一个待决项", "不展开过程", "提示可明天继续"],
    },
    "steady_problemsolve": {
        "when": "frustration",
        "tone": "先接住再解决，不辩解、不甩锅",
        "require": ["先确认问题现象", "给出根因或明确说还在查", "带 2~3 个方案回来"],
    },
    "credit_concrete": {
        "when": "celebration",
        "tone": "认可成果，顺势给下一步，不空夸",
        "require": ["具体说清成了什么", "指出还可加固的一处", "给下一步选择"],
    },
    "reanchor": {
        "when": "doubt",
        "tone": "停下来对齐目标，不硬推",
        "require": ["复述我理解的目标", "请对方确认或纠正", "说明当前偏差在哪"],
    },
}


def _load_user_style() -> dict:
    """可选：读取用户沟通偏好（由 Owner 显式设定，缺失则用默认）。"""
    f = __import__("gbt_allinone._paths", fromlist=["STORE_DIR"]).STORE_DIR / "user_style.json"
    if f.exists():
        try:
            import json
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def read_signals(text: str) -> dict:
    """识别一段用户文本里的状态信号。返回各维度命中的关键词。"""
    t = (text or "").lower()
    hits = {}
    for dim, kws in _SIGNALS.items():
        found = [k for k in kws if k.lower() in t]
        if found:
            hits[dim] = found
    return hits


def _pick_posture(hits: dict) -> str:
    """多信号并存时的优先序：紧急 > 受挫 > 怀疑 > 疲惫 > 进展。
    （紧急要快，受挫要接住，怀疑要对齐——这三类最影响沟通成败。）"""
    for dim in ("urgency", "frustration", "doubt", "fatigue", "celebration"):
        if dim in hits:
            for name, p in _POSTURES.items():
                if p["when"] == dim:
                    return name
    return "default"


def run(op="status", **params) -> dict:
    """能力入口（只读 · R-H194 补）：status / advise。**只说怎么说话，不替人说。**

    为什么补：本能力位此前没有 `run()`，编排内核接不上 ⇒ 孤儿。
    """
    op = str(op or "status")
    if op == "advise":
        return {"ok": True, "readonly": True,
                "advice": advise(params.get("user_text", ""), params.get("situation", ""))}
    if op == "status":
        return {"ok": True, "readonly": True, "module": "tactics",
                "note": "策略角色点：识别通信信号 —— 只输出『怎么说』，不替用户说话"}
    raise ValueError("未知 op %r（可用：status/advise）" % (op,))


def advise(user_text: str = "", situation: str = "") -> dict:
    """给当前沟通场景一个分寸建议。

    user_text: 用户最近的原始消息（用于识别状态）
    situation: 可选，任务侧情境（如 stalled / failed / done）
    返回：posture + tone + require（必须满足的结构）+ honesty（不可逾越的铁律）
    """
    hits = read_signals(user_text)
    posture = _pick_posture(hits)

    # 任务侧情境覆盖：卡住/失败时，无论用户情绪如何，都必须走"接住+带方案"
    if situation in ("stalled", "failed", "blocked"):
        posture = "steady_problemsolve"

    style = _load_user_style()
    if style.get("terse") and posture == "default":
        posture = "results_first"

    p = _POSTURES.get(posture, {
        "tone": "正常专业表达：结论先行，依据跟上，下一步明确",
        "require": ["结论先行", "依据可核", "下一步明确"],
    })
    return {
        "posture": posture,
        "detected": hits,
        "situation": situation or "normal",
        "tone": p["tone"],
        "require": p["require"],
        "honesty": [
            "只调表达分寸，不改任何事实与结论",
            "坏消息如实到达，不隐藏不稀释",
            "识别到困难必须带方案，不空安抚",
        ],
    }


def escalate(task: dict, reason: dict) -> dict:
    """任务卡住/失败时，生成"带着方案回来"的升级包（三律3的可执行形态）。

    不是把问题原样甩回给用户，而是：发生了什么 + 卡在哪 + 2~3 个可行方案（含代价）。
    """
    from .store import audit
    tid = task.get("task_id", "?")
    desc = task.get("description", "")
    why = task.get("last_error", "") or reason.get("error", "")

    if "fingerprint" in reason:
        kind = "stalled"
        what = f"任务 {tid}（{desc}）连续 {reason.get('repeats', 3)} 次得到同样的结果，判定卡住"
    else:
        kind = "attempts_exhausted"
        what = f"任务 {tid}（{desc}）重试 {task.get('attempts', 0)} 次仍未达标"

    options = [
        {"plan": "拆分任务", "cost": "需要把当前任务拆成更小步骤，可能要多跑几轮",
         "when": "目标正确但单步太大时"},
        {"plan": "换验收口径", "cost": "需要你确认验收标准是否过严",
         "when": "执行其实完成了，是判定标准对不上时"},
        {"plan": "先放下，人工介入", "cost": "暂停该任务，等你给新指示",
         "when": "目标本身需要重新确认时"},
    ]
    pkg = {"task_id": tid, "kind": kind, "what": what, "blocked_by": why,
           "options": options, "need": "请挑一个方向，或给我新指示"}
    audit("longrun_escalate", {"task_id": tid, "kind": kind})
    return pkg
