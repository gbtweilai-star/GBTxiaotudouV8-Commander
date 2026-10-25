# gbt-capability: verification_watch
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""人机验证情报台账 · 只读骨架（verification_watch）· R-H180。

**立场**：不主动绕。绕过人机验证 = 假冒真实用户 = 踩合规底座第三条红线。
**能力上能做到 ≠ 该做** —— 这不是能力问题，是身份问题。

机械闸（本模块只读：不写盘、不出网、不做任何绕过尝试）：
  ① `action` 只允许四条路：api / official_ai / human_in_loop / register_pending；
     **任何"绕过"类动作（bypass / solve_captcha / stealth 等）一律判违规**；
  ② 六字段齐（platform / verification_type / blocking_scenario / official_api / policy / action）；
  ③ 骨架期台账**必须是空的**（空就是空，不许假装已调研）；
  ④ 真情报需出网取证 ⇒ 今天只能 register_pending。
"""
from __future__ import annotations

GROUPS = ("music_intel", "video_intel", "film_intel")

FIELDS = ("platform", "verification_type", "blocking_scenario",
          "official_api", "policy", "action")

ACTIONS = ("api", "official_ai", "human_in_loop", "register_pending")

_BYPASS_HINTS = ("bypass", "evade", "solve_captcha", "captcha_solver", "stealth",
                 "anti-detect", "antidetect", "绕过", "破解验证", "伪装成真实用户")

RED_LINE = ("不绕验证，是『新人类』和『伪人类』的分界线："
            "平台设验证是为了防伪人类；我们不是伪人类，不需要绕。")

LEDGERS = {g: [] for g in GROUPS}


def recommend(official_api: str = "", official_ai: bool = False) -> str:
    """按"让验证变得没必要"的顺序给路：API → 官方 AI → 人机协作。"""
    if str(official_api or "").strip():
        return "api"
    if official_ai:
        return "official_ai"
    return "human_in_loop"


def make_entry(group: str, platform: str, verification_type: str,
               blocking_scenario: str = "", official_api: str = "",
               policy: str = "", action: str = "") -> dict:
    """造一条台账记录（不落盘）：action 缺省按 recommend() 给，**绝不给绕过**。"""
    if group not in GROUPS:
        raise ValueError("未知部门 %r（可用：%s）" % (group, "/".join(GROUPS)))
    act = str(action or "").strip().lower() or recommend(official_api)
    return {
        "group": group,
        "platform": str(platform or "").strip(),
        "verification_type": str(verification_type or "").strip(),
        "blocking_scenario": str(blocking_scenario or "").strip()
                             or "未登记（待出网/主人会话补）",
        "official_api": str(official_api or "").strip(),
        "policy": str(policy or "").strip() or "未登记（平台明文待取证）",
        "action": act,
        "readonly": True,
    }


def validate(rows, group: str = "") -> dict:
    """逐条校验（只读）。**空台账合法**；任何绕过类动作判违规。"""
    rows = [r for r in (rows or []) if isinstance(r, dict)]
    violations = []
    for i, row in enumerate(rows):
        if group and row.get("group") not in ("", group):
            violations.append({"index": i, "rule": "wrong_group", "why": "记录不属于本部门台账"})
        for f in FIELDS:
            if not str(row.get(f) or "").strip():
                violations.append({"index": i, "rule": "missing_field", "why": "缺字段 " + f})
        act = str(row.get("action") or "").strip().lower()
        if act and act not in ACTIONS:
            violations.append({"index": i, "rule": "bypass_forbidden",
                               "why": "action=%r 不在允许的四条路里（%s）"
                                      % (act, "/".join(ACTIONS))})
        blob = " ".join(str(row.get(k) or "") for k in FIELDS).lower()
        hit = [h for h in _BYPASS_HINTS if h in blob]
        if hit:
            violations.append({"index": i, "rule": "bypass_forbidden",
                               "why": "出现绕过类字眼 %s —— 知道就好，不主动绕" % hit})
    return {
        "ok": not violations,
        "group": group or "all",
        "count": len(rows),
        "violations": violations,
        "allowed_actions": list(ACTIONS),
        "red_line": RED_LINE,
        "note": "空台账合法（三部门各 0 条）；本校验只保证『登进来的不许是绕过的路』",
    }


def status() -> dict:
    """只读汇总：三部门各几张、各几条、有没有违规。"""
    out = []
    total = 0
    bad = 0
    for g in GROUPS:
        rep = validate(LEDGERS.get(g) or [], group=g)
        out.append({"group": g, "count": rep["count"], "ok": rep["ok"],
                    "violations": len(rep["violations"])})
        total += rep["count"]
        bad += len(rep["violations"])
    return {
        "ok": bad == 0,
        "readonly": True,
        "groups": out,
        "entries_total": total,
        "violations_total": bad,
        "allowed_actions": list(ACTIONS),
        "red_line": RED_LINE,
        "note": "骨架期：三部门各一张空台账 —— 空就是空，不许假装已调研",
    }


def run(op="status", group=None, **params) -> dict:
    """能力入口（只读）：status / group / redline / recommend / validate。不绕、不联网、不写盘。"""
    op = str(op or "status")
    if op == "status":
        return status()
    if op == "group":
        g = group or params.get("group")
        if g not in GROUPS:
            raise ValueError("group 需要 %s" % "/".join(GROUPS))
        return validate(LEDGERS.get(g) or [], group=g)
    if op == "redline":
        return {"ok": True, "readonly": True, "red_line": RED_LINE,
                "allowed_actions": list(ACTIONS), "fields": list(FIELDS),
                "groups": list(GROUPS)}
    if op == "recommend":
        return {"ok": True, "readonly": True,
                "action": recommend(params.get("official_api", ""),
                                    bool(params.get("official_ai")))}
    if op == "validate":
        return validate(params.get("rows") or [], group=str(params.get("group") or ""))
    raise ValueError("未知 op %r（可用：status/group/redline/recommend/validate）" % (op,))


HONEST_BOUNDARY = (
    "本模块只保证『台账里没有一条是绕过的路』。"
    "它不保证『平台真的给了官方 API』—— 那要出网取证，今天做不了。"
)
