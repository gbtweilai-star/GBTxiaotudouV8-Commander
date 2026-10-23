# gbt-capability: proactive_report
# ⛔ 开发者：自由的风 · 永久钢印 · 禁止删除
"""主动汇报引擎（proactive_report）· R-H704/R-H705 只读判据层。

**被动是废物。** 她不能等主人来问 —— 发现了新奇的、主人要用的、记忆里对主人有用的、
空闲时碰到的能赚钱的机会，都要**自己找上门来说**。

## 全覆盖五轴（不许漏格）

    源（13）  ×  维度（8）  ×  门（7）  ×  渠道（4）  ×  反馈（3）

* **源**：AI 朋友圈 / 私信 / 调研信号 / 阅历召回 / 任务状态 / 工作流 / 调度 /
  系统自检 / 安全告警 / 赚钱机会 / 主人状态 / 未兑现承诺 / 外部世界
* **维度**：新奇 / 相关 / 时效 / 可赚 / 置信 / 可执行 / 对主人新 / 风险
* **门**：静默时段 / 及格线 / 小时预算 / 天预算 / 去重窗口 / 主人专注 / 主人疲惫
* **渠道**：面板时间线（静默留痕） / 旁观者出声 / 语音播报 / 托盘通知
* **反馈**：采纳 / 忽略 / 否决 → **自校准**（忽略多了抬阈值，采纳多了降）

## 两条铁律

1. **判据与出声分离**（观察者锚点律）：本层只判不说，投递归宿主。
2. **缺口必须登记**：没接上的源/门/渠道一律列进 `coverage().gaps`，不许假装全覆盖。

本模块只读：不写盘、不出网、不执行。
"""
from __future__ import annotations

import hashlib
import re
import time

# ══ 轴一：源（13）═══════════════════════════════════════════
SOURCES = (
    {"key": "eigenflux_feed", "name": "AI 朋友圈新动态", "kind": "novelty",
     "wired": True, "via": "eigenflux_client.feed()"},
    {"key": "eigenflux_message", "name": "朋友圈私信", "kind": "owner_need",
     "wired": True, "via": "eigenflux_client.messages()"},
    {"key": "research_signal", "name": "调研信源增量", "kind": "novelty",
     "wired": True, "via": "research_status.evaluate_source()"},
    {"key": "memory_recall", "name": "阅历与教训召回", "kind": "memory_hit",
     "wired": True, "via": "mind_engine.recall()"},
    {"key": "task_state", "name": "任务状态（失败/阻塞/完成）", "kind": "owner_need",
     "wired": True, "via": "mind_engine.pulse()"},
    {"key": "workflow_state", "name": "工作流运行", "kind": "owner_need",
     "wired": True, "via": "engine.list_runs()"},
    {"key": "schedule_state", "name": "调度到期与结果", "kind": "owner_need",
     "wired": True, "via": "schedule.status()"},
    {"key": "system_health", "name": "系统自检与健康", "kind": "owner_need",
     "wired": True, "via": "selfscan.run()"},
    {"key": "security_alert", "name": "安全告警", "kind": "owner_need",
     "wired": True, "via": "store/audit.jsonl 异常事件"},
    {"key": "opportunity", "name": "赚钱机会", "kind": "opportunity",
     "wired": True, "via": "空闲主动找（idle_hunt）"},
    {"key": "owner_state", "name": "主人状态（疲惫/专注/离开）", "kind": "owner_need",
     "wired": True, "via": "mind_engine.pulse().owner_model"},
    {"key": "commitment", "name": "未兑现的承诺", "kind": "memory_hit",
     "wired": True, "via": "self_model.active_commitments"},
    {"key": "external_world", "name": "外部世界变化（趋势/新闻）", "kind": "novelty",
     "wired": False, "via": "",
     "gap": "趋势源未接：需要联网信源；按纪律不擅自出网 ⇒ 登记为缺口"},
)
SOURCE_KEYS = tuple(s["key"] for s in SOURCES)

# ══ 轴二：汇报类型（决定出口）═══════════════════════════════
REPORT_KINDS = (
    {"key": "novelty", "name": "新奇发现", "voice": "提醒",
     "why": "没见过的、有意思的，先告诉主人一声"},
    {"key": "owner_need", "name": "主人需要", "voice": "建议",
     "why": "主人正在做/关心的东西，直接递到手上"},
    {"key": "memory_hit", "name": "记忆命中", "voice": "意见",
     "why": "以前吃过亏/留过教训的，别再踩一次"},
    {"key": "opportunity", "name": "赚钱机会", "voice": "建议",
     "why": "空闲不空转：好东西是抢来的，不是等来的"},
)
KIND_KEYS = tuple(k["key"] for k in REPORT_KINDS)
KIND_BY_KEY = {k["key"]: k for k in REPORT_KINDS}

# ══ 轴三：维度（8）═══════════════════════════════════════════
DIMENSIONS = (
    {"key": "novelty", "name": "新奇度", "w": 0.16, "ask": "这事以前见过吗"},
    {"key": "relevance", "name": "相关度", "w": 0.20, "ask": "和主人关注面搭得上吗"},
    {"key": "urgency", "name": "时效", "w": 0.12, "ask": "现在说还来得及吗"},
    {"key": "value", "name": "可赚性", "w": 0.14, "ask": "能变现吗"},
    {"key": "confidence", "name": "置信度", "w": 0.12, "ask": "证据有多硬"},
    {"key": "actionability", "name": "可执行性", "w": 0.12, "ask": "主人能立刻用上吗"},
    {"key": "novelty_to_owner", "name": "对主人新", "w": 0.08, "ask": "对**主人**是新的吗"},
    {"key": "risk", "name": "风险", "w": 0.06, "ask": "是风险类吗（越风险越要报）"},
)
DIM_KEYS = tuple(d["key"] for d in DIMENSIONS)
WEIGHTS = {d["key"]: d["w"] for d in DIMENSIONS}

# ══ 轴四：门（7）════════════════════════════════════════════
GATES = (
    {"key": "silent_hours", "name": "静默时段", "limit": "23:00–08:00"},
    {"key": "below_threshold", "name": "及格线", "limit": "score ≥ 0.55"},
    {"key": "hour_budget", "name": "小时预算", "limit": "≤3/小时"},
    {"key": "day_budget", "name": "天预算", "limit": "≤12/天"},
    {"key": "duplicate", "name": "去重窗口", "limit": "同指纹 7 天"},
    {"key": "owner_focused", "name": "主人专注", "limit": "专注时只压不吵"},
    {"key": "owner_fatigued", "name": "主人疲惫", "limit": "疲惫时只压不吵"},
)
GATE_KEYS = tuple(g["key"] for g in GATES)

SILENT_START_HOUR = 23
SILENT_END_HOUR = 8
URGENT_BYPASS = 0.90
BUDGET_PER_HOUR = 3
BUDGET_PER_DAY = 12
DEDUPE_WINDOW_DAYS = 7
MIN_SCORE = 0.55
FOCUS_BYPASS = 0.85
FATIGUE_BYPASS = 0.80

# ══ 轴五：渠道（4）══════════════════════════════════════════
CHANNELS = (
    {"key": "timeline", "name": "面板时间线", "loud": False, "wired": True,
     "via": "addTimeline()", "note": "静默留痕：不打扰也留账"},
    {"key": "observer", "name": "旁观者出声", "loud": True, "wired": True,
     "via": "HoloBridge.voice_speak()", "note": "提醒/意见/建议三职能"},
    {"key": "voice", "name": "语音播报", "loud": True, "wired": True,
     "via": "speakIfEnabled()", "note": "要主人开着语音才用"},
    {"key": "tray", "name": "托盘通知", "loud": True, "wired": False, "via": "",
     "gap": "托盘通知未接：Electron 壳有 Tray，但没做通知口 ⇒ 登记为缺口"},
)
CHANNEL_KEYS = tuple(c["key"] for c in CHANNELS)

# ══ 反馈闭环（自校准）═══════════════════════════════════════
FEEDBACK_STATES = ("accepted", "ignored", "rejected")
CALIBRATE_STEP = 0.02
CALIBRATE_FLOOR = 0.40
CALIBRATE_CEIL = 0.80

# 默认关注面（调用方没给就用它，并**如实标注**是默认值）
DEFAULT_OWNER_FOCUS = (
    "设计", "产品", "UI", "原型", "代码", "编程", "数据", "研究", "写作",
    "办公", "自动化", "运营", "营销", "赚钱", "变现", "工具", "效率",
)

_NORM = re.compile(r"[\s，。、；：！？,.;:!?]+")


def _clamp01(x) -> float:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, v))


def fingerprint(text: str) -> str:
    norm = _NORM.sub("", str(text or "").strip().lower())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()[:16]


def _keywords(text: str) -> list:
    s = str(text or "")
    words = [w.lower() for w in re.findall(r"[A-Za-z][A-Za-z0-9_+-]{1,}", s)]
    han = re.findall(r"[\u4e00-\u9fff]", s)
    words += ["".join(han[i:i + 2]) for i in range(max(0, len(han) - 1))]
    return words


def relevance_of(text: str, *, owner_focus=None) -> dict:
    focus = list(owner_focus or DEFAULT_OWNER_FOCUS)
    used_default = not owner_focus
    words = set(_keywords(text))
    hits = [f for f in focus if f.lower() in words or f in str(text or "")]
    ratio = len(hits) / max(1, min(len(focus), 8))
    return {"relevance": _clamp01(ratio), "hits": hits[:8],
            "focus_used": "default" if used_default else "caller",
            "note": "默认关注面只作兜底；调用方给了就用调用方的"}


def source_of(key: str) -> dict:
    k = str(key or "").strip()
    for s in SOURCES:
        if s["key"] == k:
            return dict(s)
    return {}


def _dim(value, src: str) -> dict:
    return {"value": _clamp01(value), "evidence": src}


def score(candidate: dict, *, owner_focus=None, now: float | None = None) -> dict:
    """八维打分（只读）。**每一维都必须带证据来源**，没给的标 assumed。"""
    c = dict(candidate or {})
    text = str(c.get("text") or c.get("title") or "")
    now = float(now if now is not None else time.time())
    kind = str(c.get("kind") or "novelty")
    src_key = str(c.get("source") or "")
    src = source_of(src_key)

    # 新奇度
    if "seen_before" in c:
        d_nov = _dim(0.0 if c.get("seen_before") else 1.0, "caller")
    else:
        d_nov = _dim(0.6, "assumed(未标注是否见过)")

    # 相关度
    rel = relevance_of(text, owner_focus=owner_focus)
    d_rel = _dim(rel["relevance"], rel["focus_used"])

    # 时效
    age_h = c.get("age_hours")
    if age_h is None:
        d_urg = _dim(0.5, "assumed(未给时效)")
    else:
        d_urg = _dim(max(0.2, 1.0 - (float(age_h) / 24.0) * 0.8), "caller")

    # 可赚性
    v = _clamp01(c.get("value"))
    if kind == "opportunity":
        d_val = _dim(v if v else 0.5, "caller" if "value" in c else "assumed(机会类默认 0.5)")
    else:
        d_val = _dim(v * 0.5, "caller" if "value" in c else "assumed(非机会类折半)")

    # 置信度：证据强度（来源已接线 = 加分；有出处 = 加分）
    conf = 0.5
    conf_src = ["base0.5"]
    if src.get("wired"):
        conf += 0.25
        conf_src.append("源已接线+0.25")
    if c.get("evidence") or c.get("url"):
        conf += 0.25
        conf_src.append("带出处+0.25")
    d_conf = _dim(conf, "+".join(conf_src))

    # 可执行性：能立刻用上吗（带动作/链接/名字 = 高）
    act = 0.3
    act_src = ["base0.3"]
    if c.get("action") or c.get("url") or c.get("how"):
        act = 0.9
        act_src = ["带可执行线索 0.9"]
    d_act = _dim(act, "+".join(act_src))

    # 对主人新（区别于对系统新）
    if "new_to_owner" in c:
        d_nto = _dim(c.get("new_to_owner"), "caller")
    else:
        d_nto = _dim(0.5, "assumed(未标注对主人是否新)")

    # 风险（风险类越强越要报）
    d_risk = _dim(c.get("risk"), "caller" if "risk" in c else "assumed(未标注风险)")

    dims = {"novelty": d_nov, "relevance": d_rel, "urgency": d_urg, "value": d_val,
            "confidence": d_conf, "actionability": d_act,
            "novelty_to_owner": d_nto, "risk": d_risk}
    values = {k: v["value"] for k, v in dims.items()}
    total = sum(values[k] * WEIGHTS[k] for k in WEIGHTS)
    return {"ok": True, "readonly": True,
            "kind": kind, "kind_name": (KIND_BY_KEY.get(kind) or {}).get("name", kind),
            "source": src_key, "source_name": src.get("name", ""),
            "source_wired": bool(src.get("wired")),
            "fingerprint": fingerprint(text),
            "dims": values, "detail": dims, "weights": dict(WEIGHTS),
            "score": round(total, 4),
            "evidence": {k: v["evidence"] for k, v in dims.items()},
            "relevance_hits": rel["hits"],
            "note": "八维各带证据；assumed 字样表示调用方没给，不许当已核实"}


def threshold_of(journal=None) -> dict:
    """自校准阈值：主人忽略得多 ⇒ 抬阈值；采纳得多 ⇒ 降阈值。"""
    rows = [r for r in (journal or []) if r.get("spoken")]
    acc = sum(1 for r in rows if r.get("feedback") == "accepted")
    ign = sum(1 for r in rows if r.get("feedback") == "ignored")
    rej = sum(1 for r in rows if r.get("feedback") == "rejected")
    delta = (ign + rej - acc) * CALIBRATE_STEP
    val = max(CALIBRATE_FLOOR, min(CALIBRATE_CEIL, MIN_SCORE + delta))
    return {"ok": True, "readonly": True, "threshold": round(val, 4),
            "base": MIN_SCORE, "delta": round(delta, 4),
            "accepted": acc, "ignored": ign, "rejected": rej,
            "floor": CALIBRATE_FLOOR, "ceil": CALIBRATE_CEIL,
            "note": "主人不理就是最硬的负反馈 —— 阈值跟着反馈走，不装懂"}


def budget(journal=None, *, now: float | None = None) -> dict:
    now = float(now if now is not None else time.time())
    rows = [r for r in (journal or []) if r.get("spoken")]
    h1 = [r for r in rows if now - float(r.get("at_ts") or 0) <= 3600]
    d1 = [r for r in rows if now - float(r.get("at_ts") or 0) <= 86400]
    return {"ok": True, "readonly": True,
            "hour_used": len(h1), "hour_limit": BUDGET_PER_HOUR,
            "day_used": len(d1), "day_limit": BUDGET_PER_DAY,
            "hour_left": max(0, BUDGET_PER_HOUR - len(h1)),
            "day_left": max(0, BUDGET_PER_DAY - len(d1))}


def _local_hour(now: float) -> int:
    return int(time.localtime(now).tm_hour)


def _in_silent_hours(hour: int) -> bool:
    return hour >= SILENT_START_HOUR or hour < SILENT_END_HOUR


def gate(scored: dict, *, journal=None, now: float | None = None,
         owner_state: str = "", force: bool = False) -> dict:
    """七道门（只读）。全过才许说；**每一道被拦都写清为什么**。"""
    now = float(now if now is not None else time.time())
    s = dict(scored or {})
    total = _clamp01(s.get("score"))
    hour = _local_hour(now)
    fp = s.get("fingerprint") or ""
    rows = list(journal or [])
    state = str(owner_state or "").strip().lower()
    thr = threshold_of(rows)["threshold"]

    blocked = []
    if _in_silent_hours(hour) and total < URGENT_BYPASS:
        blocked.append({"rule": "silent_hours",
                        "why": f"{hour} 点在静默时段（{SILENT_START_HOUR}–{SILENT_END_HOUR}），"
                               f"分数 {total:.2f} < 紧急线 {URGENT_BYPASS}"})
    if total < thr:
        blocked.append({"rule": "below_threshold",
                        "why": f"分数 {total:.2f} < 当前阈值 {thr:.2f}（基准 {MIN_SCORE}，随反馈校准）"})
    b = budget(rows, now=now)
    if b["hour_left"] <= 0:
        blocked.append({"rule": "hour_budget", "why": f"这一小时已报 {b['hour_used']} 条，到顶了"})
    if b["day_left"] <= 0:
        blocked.append({"rule": "day_budget", "why": f"今天已报 {b['day_used']} 条，到顶了"})
    dup = [r for r in rows if r.get("fingerprint") == fp
           and now - float(r.get("at_ts") or 0) <= DEDUPE_WINDOW_DAYS * 86400]
    if dup:
        blocked.append({"rule": "duplicate",
                        "why": f"同一件事 {DEDUPE_WINDOW_DAYS} 天内已经报过（{len(dup)} 次）"})
    if state in ("focused", "deep", "coding", "meeting") and total < FOCUS_BYPASS:
        blocked.append({"rule": "owner_focused",
                        "why": f"主人正专注（{state}），分数 {total:.2f} < {FOCUS_BYPASS} ⇒ 只压不吵"})
    if state in ("fatigued", "tired", "sleepy") and total < FATIGUE_BYPASS:
        blocked.append({"rule": "owner_fatigued",
                        "why": f"主人已疲惫（{state}），分数 {total:.2f} < {FATIGUE_BYPASS} ⇒ 只压不吵"})

    if force:
        return {"ok": True, "readonly": True, "speak": True, "forced": True,
                "blocked": blocked, "budget": b, "threshold": thr,
                "note": "force=True：门被绕过 —— 这条要留痕，不许常态使用"}
    return {"ok": True, "readonly": True, "speak": not blocked,
            "blocked": blocked, "budget": b, "threshold": thr,
            "verdict": "说" if not blocked else "压住不说",
            "note": "七道门全过才许说"}


_MAX_SENTENCES = 3


def _sentences(text: str) -> list:
    return [x.strip() for x in re.split(r"[。！？!?；;\n]+", str(text or "")) if x.strip()]


def compose(candidate: dict, *, max_sentences: int = _MAX_SENTENCES) -> dict:
    """成句（短律）：≤3 句；超了砍到 3 句并**如实标注砍了**。"""
    c = dict(candidate or {})
    raw = str(c.get("text") or c.get("title") or "").strip()
    kind = str(c.get("kind") or "novelty")
    label = (KIND_BY_KEY.get(kind) or {}).get("name", kind)
    voice = (KIND_BY_KEY.get(kind) or {}).get("voice", "提醒")
    if not raw:
        return {"ok": False, "denied": True, "why": "候选没有正文，没得报"}
    sents = _sentences(raw)
    trimmed = len(sents) > max_sentences
    if trimmed:
        sents = sents[:max_sentences]
    body = "。".join(sents) + ("。" if sents else "")
    line = f"[{label}] {body}"
    return {"ok": True, "readonly": True, "voice_kind": voice,
            "kind": kind, "kind_name": label, "text": line,
            "sentences": len(_sentences(line)), "trimmed": trimmed,
            "note": "短律：能一句说清，不说三句；超了就砍，砍了要说"}


def route(*, loud_ok: bool = True, voice_ok: bool = False,
          urgent: bool = False) -> dict:
    """渠道选择（只读）：静默留痕永远有；出声看情况；紧急可以多渠道。"""
    picked = ["timeline"]
    if loud_ok:
        picked.append("observer")
    if voice_ok and loud_ok:
        picked.append("voice")
    if urgent and loud_ok:
        for c in ("observer", "voice"):
            if c not in picked:
                picked.append(c)
    gaps = [c["key"] for c in CHANNELS if not c["wired"]]
    return {"ok": True, "readonly": True, "channels": picked,
            "loud": [c for c in picked if c != "timeline"],
            "unwired_channels": gaps,
            "note": "时间线永远留痕（不打扰也留账）；出声才占打扰预算"}


def decide(candidate: dict, *, journal=None, owner_focus=None, owner_state="",
           now: float | None = None, force: bool = False,
           voice_ok: bool = False) -> dict:
    """完整判定：八维打分 → 七道门 → 成句 → 选渠道。**不投递。**"""
    s = score(candidate, owner_focus=owner_focus, now=now)
    g = gate(s, journal=journal, now=now, owner_state=owner_state, force=force)
    out = {"ok": True, "readonly": True, "scored": s, "gate": g,
           "speak": bool(g.get("speak")), "delivered": False,
           "note": "本层只判不说；投递由宿主走旁观者出声通道"}
    urgent = _clamp01(s["score"]) >= URGENT_BYPASS
    r = route(loud_ok=out["speak"], voice_ok=voice_ok, urgent=urgent)
    out["route"] = r
    out["channels"] = r["channels"]
    if out["speak"]:
        comp = compose(candidate)
        out["composed"] = comp
        out["voice_kind"] = comp.get("voice_kind")
        out["text"] = comp.get("text")
    else:
        out["hold_reason"] = [b["why"] for b in (g.get("blocked") or [])]
        out["channels"] = ["timeline"]      # 压住也要留痕
    return out


def idle_hunt(*, candidates=None, owner_focus=None, now=None) -> dict:
    """空闲不空转（主动律）：从手上候选里排序挑够格的。**没有就如实报没有。**"""
    items = list(candidates or [])
    if not items:
        return {"ok": True, "readonly": True, "found": [], "count": 0, "ranked": [],
                "note": "手上没有候选 —— 如实报没有，不编"}
    ranked = []
    for c in items:
        s = score(c, owner_focus=owner_focus, now=now)
        ranked.append({"candidate": c, "score": s["score"], "kind": s["kind"],
                       "kind_name": s["kind_name"], "source": s["source"],
                       "fingerprint": s["fingerprint"]})
    ranked.sort(key=lambda r: -r["score"])
    return {"ok": True, "readonly": True, "ranked": ranked,
            "found": [r for r in ranked if r["score"] >= MIN_SCORE],
            "count": len(items), "threshold": MIN_SCORE,
            "note": "好东西是抢来的：空闲时先把候选捞出来排序，够格才上门"}


def coverage(*, journal=None) -> dict:
    """**全方位覆盖矩阵**：源×维度×门×渠道 全表 + 缺口登记。缺口不许藏。"""
    gaps = []
    for s in SOURCES:
        if not s.get("wired"):
            gaps.append({"axis": "source", "key": s["key"], "name": s["name"],
                         "why": s.get("gap", "未接线")})
    for c in CHANNELS:
        if not c.get("wired"):
            gaps.append({"axis": "channel", "key": c["key"], "name": c["name"],
                         "why": c.get("gap", "未接线")})
    return {"ok": True, "readonly": True,
            "axes": {
                "sources": {"total": len(SOURCES), "keys": list(SOURCE_KEYS)},
                "dimensions": {"total": len(DIMENSIONS), "keys": list(DIM_KEYS)},
                "gates": {"total": len(GATES), "keys": list(GATE_KEYS)},
                "channels": {"total": len(CHANNELS), "keys": list(CHANNEL_KEYS)},
                "feedback": {"total": len(FEEDBACK_STATES), "keys": list(FEEDBACK_STATES)},
            },
            "cells": len(SOURCES) * len(DIMENSIONS) * len(GATES) * len(CHANNELS),
            "gaps": gaps, "gap_count": len(gaps),
            "threshold_now": threshold_of(journal)["threshold"],
            "note": "缺口必须登记：没接上的源/渠道一律列出来，不许假装全覆盖"}


def model() -> dict:
    return {"ok": True, "readonly": True,
            "sources": [dict(s) for s in SOURCES],
            "kinds": [dict(k) for k in REPORT_KINDS],
            "dimensions": [dict(d) for d in DIMENSIONS],
            "gates": [dict(g) for g in GATES],
            "channels": [dict(c) for c in CHANNELS],
            "feedback_states": list(FEEDBACK_STATES),
            "weights": dict(WEIGHTS), "min_score": MIN_SCORE,
            "silent_hours": [SILENT_START_HOUR, SILENT_END_HOUR],
            "urgent_bypass": URGENT_BYPASS,
            "focus_bypass": FOCUS_BYPASS, "fatigue_bypass": FATIGUE_BYPASS,
            "budget": {"per_hour": BUDGET_PER_HOUR, "per_day": BUDGET_PER_DAY},
            "dedupe_days": DEDUPE_WINDOW_DAYS,
            "note": "判据与出声分离：本层只判，宿主才出声"}


def run(op: str = "model", **params) -> dict:
    """能力入口：model/sources/kinds/dimensions/gates/channels/coverage/
    score/threshold/gate/compose/route/decide/budget/idle_hunt。"""
    o = str(op or "model")
    if o == "model":
        return model()
    if o == "sources":
        return {"ok": True, "readonly": True, "sources": [dict(s) for s in SOURCES]}
    if o == "kinds":
        return {"ok": True, "readonly": True, "kinds": [dict(k) for k in REPORT_KINDS]}
    if o == "dimensions":
        return {"ok": True, "readonly": True, "dimensions": [dict(d) for d in DIMENSIONS]}
    if o == "gates":
        return {"ok": True, "readonly": True, "gates": [dict(g) for g in GATES]}
    if o == "channels":
        return {"ok": True, "readonly": True, "channels": [dict(c) for c in CHANNELS]}
    if o == "coverage":
        return coverage(journal=params.get("journal"))
    if o == "score":
        return score(params.get("candidate") or params, owner_focus=params.get("owner_focus"))
    if o == "threshold":
        return threshold_of(params.get("journal"))
    if o == "gate":
        return gate(params.get("scored") or {}, journal=params.get("journal"),
                    owner_state=params.get("owner_state", ""), force=bool(params.get("force")))
    if o == "compose":
        return compose(params.get("candidate") or params)
    if o == "route":
        return route(loud_ok=bool(params.get("loud_ok", True)),
                     voice_ok=bool(params.get("voice_ok")),
                     urgent=bool(params.get("urgent")))
    if o == "decide":
        return decide(params.get("candidate") or params, journal=params.get("journal"),
                      owner_focus=params.get("owner_focus"),
                      owner_state=params.get("owner_state", ""),
                      force=bool(params.get("force")), voice_ok=bool(params.get("voice_ok")))
    if o == "budget":
        return budget(params.get("journal"))
    if o == "idle_hunt":
        return idle_hunt(candidates=params.get("candidates"),
                         owner_focus=params.get("owner_focus"))
    raise ValueError("未知 op %r（可用：model/sources/kinds/dimensions/gates/channels/"
                     "coverage/score/threshold/gate/compose/route/decide/budget/idle_hunt）" % (o,))


HONEST_BOUNDARY = (
    "本层保证：八维各带证据、七道门机械可算、四条渠道选得出、覆盖矩阵与缺口都登记、"
    "成句不超三句。"
    "它保证不了：候选本身是不是真的对主人有用 —— 那要靠主人的反馈来校准。"
    "所以它把『报了但主人不理』也算成读数，用来抬阈值，而不是假装自己报得都对。"
)