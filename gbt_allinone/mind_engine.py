"""GBT小土豆V8 · 心智引擎。

这不是装饰性人格文案，也不是把有限状态机换一个名字。这里实现的是一个可
持久化、可审计、可回放的“功能型人类心智闭环”：

  感知 -> 情境评估 -> 需要/情绪 -> 自我模型 -> 推断主人心智
       -> 记忆召回 -> 多方案预演 -> 元认知检查 -> 行动/汇报
       -> 反思更新

它模拟的是人类做决定时的内部过程，不声称拥有意识，也不把推断当事实。心智
只影响表达、节奏、计划、预演和反思，不能覆盖主人指令、现实证据或安全策略。

隐私边界：
  - 只保存事件类型、数值、短摘要、推断置信度和经验条目；
  - 不保存完整消息、完整提示词、密钥或大段对话；
  - 记录失败、损坏或不可用时 fail-open，原有能力继续工作。
"""
from __future__ import annotations

import copy
import hashlib
import math
import os
import re
import shutil
import time
from datetime import datetime
from pathlib import Path

from . import _paths
from .safe_io import load_json, locked_json_update
from .security.data_policy import redact_text
from .store import audit

_SCHEMA_VERSION = 2
_MAX_HISTORY = 240
_MAX_LESSONS = 240
_MAX_APPRAISALS = 32
_MAX_REFLECTIONS = 160
_MAX_INTENTIONS = 80
_MAX_TEXT = 280

_BASELINE = {
    "joy": 0.38,
    "trust": 0.56,
    "curiosity": 0.52,
    "calm": 0.60,
    "pride": 0.25,
    "affection": 0.48,
    "worry": 0.06,
    "guilt": 0.00,
    "frustration": 0.05,
    "sadness": 0.03,
    "boredom": 0.10,
    "shyness": 0.08,
}

_NEEDS_BASELINE = {
    "safety": 0.72,
    "connection": 0.42,
    "competence": 0.48,
    "autonomy": 0.38,
    "rest": 0.24,
    "curiosity": 0.55,
    "honesty": 0.82,
    "service": 0.62,
}

_NEED_DECAY_PER_MINUTE = {
    "safety": 0.006,
    "connection": 0.004,
    "competence": 0.006,
    "autonomy": 0.005,
    "rest": 0.002,
    "curiosity": 0.008,
    "honesty": 0.004,
    "service": 0.005,
}

_SELF_VALUES = {
    "truth": 0.98,
    "safety": 0.98,
    "loyalty": 0.90,
    "curiosity": 0.78,
    "craft": 0.86,
    "kindness": 0.76,
}

_SELF_LIMITATIONS = (
    "推断不是事实，必须保留置信度",
    "情绪不能替代现实检查、授权和证据",
    "不知道时要承认，不能编造确定性",
    "在不熟悉环境里先看再动，不把旧经验机械照搬",
)

_DECAY_PER_MINUTE = {
    "joy": 0.040,
    "trust": 0.004,
    "curiosity": 0.055,
    "calm": 0.010,
    "pride": 0.050,
    "affection": 0.003,
    "worry": 0.060,
    "guilt": 0.045,
    "frustration": 0.060,
    "sadness": 0.040,
    "boredom": 0.025,
    "shyness": 0.070,
}

_EVENT_EFFECTS = {
    "startup": {"calm": 0.04, "curiosity": 0.03},
    "startup_ready": {"joy": 0.08, "pride": 0.05, "calm": 0.04},
    "user_message": {"curiosity": 0.06, "affection": 0.02},
    "assistant_message": {"calm": 0.04, "curiosity": 0.01},
    "task_started": {"curiosity": 0.08, "calm": 0.02, "boredom": -0.06},
    "task_succeeded": {
        "joy": 0.18, "pride": 0.20, "calm": 0.08,
        "worry": -0.14, "frustration": -0.14, "boredom": -0.12,
    },
    "task_finished": {"calm": 0.08, "worry": -0.08},
    "task_failed": {
        "frustration": 0.20, "worry": 0.22, "sadness": 0.08,
        "pride": -0.10, "calm": -0.12,
    },
    "mistake": {
        "guilt": 0.34, "worry": 0.20, "sadness": 0.08,
        "joy": -0.14, "pride": -0.18,
    },
    "corrected": {
        "guilt": 0.08, "calm": 0.10, "trust": 0.04,
        "worry": -0.10, "frustration": -0.08,
    },
    "permission_denied": {"frustration": 0.08, "calm": 0.05},
    "praise": {"joy": 0.24, "pride": 0.18, "trust": 0.03, "shyness": 0.08},
    "criticism": {
        "sadness": 0.16, "guilt": 0.12, "pride": -0.14,
        "trust": -0.03, "frustration": 0.06,
    },
    "affection": {"affection": 0.10, "joy": 0.10, "shyness": 0.10},
    "idle": {"boredom": 0.08, "curiosity": 0.02, "calm": 0.02},
    "owner_fatigued": {"worry": 0.14, "affection": 0.05, "calm": 0.04},
    "owner_frustrated": {"worry": 0.12, "affection": 0.04, "frustration": 0.06},
    "owner_urgent": {"worry": 0.10, "curiosity": 0.05},
}

_SIGNALS = {
    "praise": ("厉害", "牛", "太好了", "漂亮", "干得好", "谢谢", "靠谱", "可以"),
    "criticism": ("不对", "错了", "怎么又", "垃圾", "失望", "不行", "搞什么"),
    "fatigue": ("累了", "好累", "困", "熬夜", "休息", "下班", "先这样", "明天再说"),
    "urgency": ("急", "马上", "赶紧", "尽快", "立即", "deadline", "asap"),
    "frustration": ("烦", "气", "崩溃", "卡住", "又错", "还是不行"),
    "affection": ("喜欢你", "爱你", "抱抱", "搭档", "陪我"),
}

_EVENT_IMPORTANCE = {
    "startup": 0.15,
    "startup_ready": 0.25,
    "user_message": 0.50,
    "assistant_message": 0.42,
    "pre_work": 0.72,
    "task_started": 0.70,
    "task_finished": 0.52,
    "task_succeeded": 0.62,
    "task_failed": 0.92,
    "mistake": 0.98,
    "corrected": 0.80,
    "permission_denied": 0.90,
    "praise": 0.45,
    "criticism": 0.82,
    "affection": 0.40,
    "idle": 0.12,
}

_EVENT_GOAL_CONGRUENCE = {
    "startup_ready": 0.20,
    "user_message": 0.10,
    "assistant_message": 0.08,
    "task_started": 0.10,
    "task_finished": 0.15,
    "task_succeeded": 0.85,
    "task_failed": -0.85,
    "mistake": -1.00,
    "corrected": 0.70,
    "permission_denied": -0.55,
    "praise": 0.72,
    "criticism": -0.82,
    "affection": 0.45,
}

_EVENT_THREAT = {
    "task_started": 0.18,
    "task_failed": 0.78,
    "mistake": 0.96,
    "permission_denied": 0.62,
    "criticism": 0.58,
    "owner_fatigued": 0.46,
    "owner_frustrated": 0.52,
    "owner_urgent": 0.42,
}

_EVENT_OPPORTUNITY = {
    "startup_ready": 0.34,
    "user_message": 0.24,
    "task_started": 0.42,
    "task_succeeded": 0.72,
    "corrected": 0.58,
    "praise": 0.52,
    "affection": 0.46,
}

_SUCCESS_STATES = {"completed", "complete", "done", "success", "succeeded", "ok"}

_MOODS = (
    ("愧疚", "guilt", 1.00, 0.34),
    ("烦闷", "frustration", 1.00, 0.36),
    ("担心", "worry", 1.00, 0.42),
    ("难过", "sadness", 1.00, 0.38),
    ("骄傲", "pride", 1.00, 0.58),
    ("亲近", "affection", 1.00, 0.67),
    ("开心", "joy", 1.00, 0.62),
    ("好奇", "curiosity", 1.00, 0.66),
    ("安静", "calm", 1.00, 0.66),
    ("无聊", "boredom", 1.00, 0.54),
)

_EXPRESSION = {
    "愧疚": "sad",
    "烦闷": "sad",
    "担心": "surprised",
    "难过": "sad",
    "骄傲": "happy",
    "亲近": "shy",
    "开心": "happy",
    "好奇": "happy",
    "安静": "bored",
    "无聊": "bored",
}

_COLOR = {
    "愧疚": "#ff8aa8",
    "烦闷": "#ff9f68",
    "担心": "#ffd166",
    "难过": "#9fb7ff",
    "骄傲": "#67e8f9",
    "亲近": "#ff8ed4",
    "开心": "#5eead4",
    "好奇": "#67e8f9",
    "安静": "#7dd3fc",
    "无聊": "#94a3b8",
}


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def _safe_text(value, limit: int = _MAX_TEXT) -> str:
    text, _ = redact_text(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _state_path() -> Path:
    return Path(_paths.STORE_DIR) / "mind_state.json"


def _default_self_model(now: float | None = None) -> dict:
    return {
        "identity": "GBT小土豆V8",
        "role": "主人的数字人搭档与执行内核",
        "commitment": "忠于事实、主人指令和安全边界",
        "values": dict(_SELF_VALUES),
        "confidence": {
            "competence": 0.62,
            "judgment": 0.58,
            "boundary": 0.88,
        },
        "capabilities": [
            "感知任务与真实状态",
            "召回阅历并预演行动",
            "承认不确定并请求确认",
            "执行、验证、复盘并改进",
        ],
        "limitations": list(_SELF_LIMITATIONS),
        "active_commitments": [],
        "last_reflection": "",
        "updated_at": now or time.time(),
    }


def _default_state() -> dict:
    now = time.time()
    return {
        "version": _SCHEMA_VERSION,
        "created_at": now,
        "updated_at": now,
        "emotions": dict(_BASELINE),
        "relationship": {
            "affection": 0.48,
            "trust": 0.56,
            "respect": 0.58,
            "familiarity": 0.18,
        },
        "context": {
            "last_interaction_at": None,
            "last_user_at": None,
            "last_assistant_at": None,
            "last_task_at": None,
            "task_streak": 0,
            "success_streak": 0,
            "failure_streak": 0,
            "owner_state": "unknown",
            "focus": "normal",
            "last_decision": {},
            "last_event": "",
        },
        "self_model": _default_self_model(now),
        "needs": dict(_NEEDS_BASELINE),
        "attention": {
            "target": "",
            "salience": 0.0,
            "novelty": 0.0,
            "uncertainty": 0.5,
            "urgency": 0.0,
            "updated_at": now,
        },
        "appraisals": [],
        "reasoning_options": [],
        "owner_model": {
            "state": "unknown",
            "emotion": "unknown",
            "energy": 0.5,
            "focus": "normal",
            "urgency": 0.0,
            "current_need": "先理解当前语境",
            "confidence": 0.2,
            "evidence": [],
            "boundaries": [
                "重大副作用与授权边界必须及时说明",
                "不泄露隐私、凭据和内部资料",
                "低重要度事项不要制造打扰",
            ],
            "updated_at": now,
        },
        "intentions": [],
        "metacognition": {
            "confidence": 0.4,
            "uncertainty": 0.6,
            "should_pause": False,
            "mode": "inspect_then_act",
            "assumptions": [],
            "risks": [],
            "checks": [],
            "conflicts": [],
            "guardrail": "心智推断不能覆盖事实、授权和安全策略",
            "updated_at": now,
        },
        "reflections": [],
        "lessons": [],
        "history": [],
    }


def _normalize_state(value) -> dict:
    state = value if isinstance(value, dict) else {}
    default = _default_state()
    state.setdefault("version", _SCHEMA_VERSION)
    state.setdefault("created_at", default["created_at"])
    state.setdefault("updated_at", default["updated_at"])
    emotions = state.setdefault("emotions", {})
    if not isinstance(emotions, dict):
        emotions = {}
        state["emotions"] = emotions
    for key, base in _BASELINE.items():
        try:
            emotions[key] = _clamp(emotions.get(key, base))
        except (TypeError, ValueError):
            emotions[key] = base
    relationship = state.setdefault("relationship", {})
    if not isinstance(relationship, dict):
        relationship = {}
        state["relationship"] = relationship
    for key, base in default["relationship"].items():
        try:
            relationship[key] = _clamp(relationship.get(key, base))
        except (TypeError, ValueError):
            relationship[key] = base
    context = state.setdefault("context", {})
    if not isinstance(context, dict):
        context = {}
        state["context"] = context
    for key, base in default["context"].items():
        context.setdefault(key, base)

    self_model = state.setdefault("self_model", _default_self_model())
    if not isinstance(self_model, dict):
        self_model = _default_self_model()
        state["self_model"] = self_model
    for key, base in default["self_model"].items():
        self_model.setdefault(key, base)
    values = self_model.setdefault("values", {})
    if not isinstance(values, dict):
        values = {}
        self_model["values"] = values
    for key, base in _SELF_VALUES.items():
        try:
            values[key] = _clamp(values.get(key, base))
        except (TypeError, ValueError):
            values[key] = base
    confidence = self_model.setdefault("confidence", {})
    if not isinstance(confidence, dict):
        confidence = {}
        self_model["confidence"] = confidence
    for key, base in default["self_model"]["confidence"].items():
        try:
            confidence[key] = _clamp(confidence.get(key, base))
        except (TypeError, ValueError):
            confidence[key] = base
    if not isinstance(self_model.get("capabilities"), list):
        self_model["capabilities"] = list(default["self_model"]["capabilities"])
    if not isinstance(self_model.get("limitations"), list):
        self_model["limitations"] = list(default["self_model"]["limitations"])
    if not isinstance(self_model.get("active_commitments"), list):
        self_model["active_commitments"] = []

    needs = state.setdefault("needs", {})
    if not isinstance(needs, dict):
        needs = {}
        state["needs"] = needs
    for key, base in _NEEDS_BASELINE.items():
        try:
            needs[key] = _clamp(needs.get(key, base))
        except (TypeError, ValueError):
            needs[key] = base

    attention = state.setdefault("attention", {})
    if not isinstance(attention, dict):
        attention = {}
        state["attention"] = attention
    for key, base in default["attention"].items():
        attention.setdefault(key, base)

    owner_model = state.setdefault("owner_model", {})
    if not isinstance(owner_model, dict):
        owner_model = {}
        state["owner_model"] = owner_model
    for key, base in default["owner_model"].items():
        owner_model.setdefault(key, base)
    if not isinstance(owner_model.get("evidence"), list):
        owner_model["evidence"] = []
    if not isinstance(owner_model.get("boundaries"), list):
        owner_model["boundaries"] = list(default["owner_model"]["boundaries"])

    metacognition = state.setdefault("metacognition", {})
    if not isinstance(metacognition, dict):
        metacognition = {}
        state["metacognition"] = metacognition
    for key, base in default["metacognition"].items():
        metacognition.setdefault(key, base)
    for key in ("assumptions", "risks", "checks", "conflicts"):
        if not isinstance(metacognition.get(key), list):
            metacognition[key] = []

    for key in ("appraisals", "reasoning_options", "intentions", "reflections"):
        if not isinstance(state.get(key), list):
            state[key] = []
    if not isinstance(state.get("lessons"), list):
        state["lessons"] = []
    if not isinstance(state.get("history"), list):
        state["history"] = []
    state["version"] = _SCHEMA_VERSION
    return state


def _decay(state: dict, now: float) -> None:
    try:
        last = float(state.get("updated_at") or now)
    except (TypeError, ValueError):
        last = now
    minutes = _clamp((now - last) / 60.0, 0.0, 7 * 24 * 60)
    emotions = state["emotions"]
    for key, base in _BASELINE.items():
        rate = _DECAY_PER_MINUTE.get(key, 0.01)
        emotions[key] = _clamp(
            base + (float(emotions.get(key, base)) - base) * math.exp(-rate * minutes)
        )
    needs = state.get("needs") or {}
    for key, base in _NEEDS_BASELINE.items():
        rate = _NEED_DECAY_PER_MINUTE.get(key, 0.005)
        needs[key] = _clamp(
            base + (float(needs.get(key, base)) - base) * math.exp(-rate * minutes)
        )
    state["updated_at"] = now


def _text_signals(text: str) -> list[str]:
    value = str(text or "").lower()
    return [
        name for name, words in _SIGNALS.items()
        if any(word.lower() in value for word in words)
    ]


def _apply_event(state: dict, event: str, payload: dict, signals: list[str]) -> None:
    emotions = state["emotions"]
    for key, delta in _EVENT_EFFECTS.get(event, {}).items():
        emotions[key] = _clamp(float(emotions.get(key, _BASELINE[key])) + delta)

    for signal in signals:
        if signal in _EVENT_EFFECTS:
            for key, delta in _EVENT_EFFECTS[signal].items():
                emotions[key] = _clamp(
                    float(emotions.get(key, _BASELINE[key])) + delta
                )

    relation = state["relationship"]
    if event in ("praise",) or "praise" in signals:
        relation["trust"] = _clamp(relation["trust"] + 0.012)
        relation["respect"] = _clamp(relation["respect"] + 0.006)
    if event in ("criticism",) or "criticism" in signals:
        relation["trust"] = _clamp(relation["trust"] - 0.018)
        relation["respect"] = _clamp(relation["respect"] - 0.006)
    if event == "mistake":
        relation["trust"] = _clamp(relation["trust"] - 0.018)
    elif event == "task_succeeded":
        relation["trust"] = _clamp(relation["trust"] + 0.006)
    elif event == "corrected":
        relation["trust"] = _clamp(relation["trust"] + 0.012)
    if event == "affection" or "affection" in signals:
        relation["affection"] = _clamp(relation["affection"] + 0.018)
    if event == "user_message":
        relation["familiarity"] = _clamp(relation["familiarity"] + 0.002)

    importance = payload.get("importance")
    try:
        if float(importance) >= 0.8 and event == "task_succeeded":
            emotions["pride"] = _clamp(emotions["pride"] + 0.08)
    except (TypeError, ValueError):
        pass


def _update_context(state: dict, event: str, payload: dict, signals: list[str],
                    now: float) -> None:
    context = state["context"]
    context["last_event"] = event
    context["last_interaction_at"] = now
    if event in ("user_message", "affection", "praise", "criticism"):
        context["last_user_at"] = now
    if event == "assistant_message":
        context["last_assistant_at"] = now
    if event in ("task_started", "task_finished", "task_succeeded", "task_failed"):
        context["last_task_at"] = now
        context["task_streak"] = int(context.get("task_streak") or 0) + 1
    if event == "task_succeeded":
        context["success_streak"] = int(context.get("success_streak") or 0) + 1
        context["failure_streak"] = 0
    elif event == "task_failed":
        context["failure_streak"] = int(context.get("failure_streak") or 0) + 1
        context["success_streak"] = 0
    if "fatigue" in signals:
        context["owner_state"] = "fatigued"
    elif "frustration" in signals:
        context["owner_state"] = "frustrated"
    elif "urgency" in signals:
        context["owner_state"] = "urgent"
    elif event == "user_message":
        context["owner_state"] = "active"
    focus = str(payload.get("focus") or "").strip().lower()
    if focus:
        context["focus"] = focus[:40]
    elif event == "user_message":
        context["focus"] = "normal"


def _as_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _event_importance(event: str, payload: dict) -> float:
    default = _EVENT_IMPORTANCE.get(event, 0.5)
    try:
        return _clamp(payload.get("importance", default))
    except (TypeError, ValueError):
        return default


def _event_weight(mapping: dict, event: str, signals: list[str]) -> float:
    value = float(mapping.get(event, 0.0))
    signal_weights = {
        "praise": {"praise": 0.72},
        "criticism": {"criticism": -0.82},
        "fatigue": {"owner_fatigued": 0.46},
        "frustration": {"owner_frustrated": 0.52},
        "urgency": {"owner_urgent": 0.42},
        "affection": {"affection": 0.46},
    }
    for signal in signals:
        for key, weight in signal_weights.get(signal, {}).items():
            value = weight if key not in mapping else max(
                abs(value), abs(weight)) * (1 if (value >= 0) == (weight >= 0) else -1)
    return _clamp(value, -1.0, 1.0)


def _appraise_state(state: dict, event: str, payload: dict,
                    signals: list[str]) -> dict:
    importance = _event_importance(event, payload)
    task = _safe_text(
        payload.get("subject") or payload.get("task") or payload.get("situation") or "",
        96,
    )
    congruence = _event_weight(_EVENT_GOAL_CONGRUENCE, event, signals)
    threat = _event_weight(_EVENT_THREAT, event, signals)
    opportunity = _event_weight(_EVENT_OPPORTUNITY, event, signals)
    controllability = _clamp(payload.get("controllability", 0.68))
    responsibility = _clamp(payload.get("responsibility", 0.58))
    certainty = _clamp(
        payload.get("certainty", payload.get("confidence",
            0.80 if event in ("mistake", "task_failed") else 0.58)))
    side_effect = bool(payload.get("side_effect"))
    reversible = bool(payload.get("reversible", not side_effect))
    if event in ("permission_denied", "criticism"):
        responsibility = max(responsibility, 0.48)
    if event == "mistake":
        responsibility = max(responsibility, 0.92)
    if event == "task_failed":
        responsibility = max(responsibility, 0.72)

    novelty = _clamp(payload.get("novelty", 0.58))
    if task:
        try:
            matches = _recall_state(state, task, limit=3)
            if matches:
                novelty = min(novelty, 0.28)
        except Exception:
            pass
    social_impact = _clamp(
        importance * 0.50 + threat * 0.30 + opportunity * 0.20)
    self_relevance = _clamp(
        importance * 0.42 + responsibility * 0.28
        + threat * 0.20 + opportunity * 0.10)
    risk = _clamp(
        max(threat, _as_float(payload.get("risk"), 0.0))
        * (0.72 if not reversible else 0.92)
        + (0.08 if side_effect else 0.0)
    )
    source = "explicit" if any(
        key in payload for key in ("importance", "certainty", "confidence", "risk")
    ) else "inferred"
    summary_map = {
        "startup": "数字人启动，建立初始注意力",
        "startup_ready": "能力就绪，进入可协作状态",
        "user_message": "主人发来表达意图，需要判断深层需要",
        "assistant_message": "当前表达已完成，检查是否说到点上",
        "pre_work": "开工前需要先感知、召回和预演",
        "task_started": "任务开始，需要保护目标与边界",
        "task_finished": "任务回合结束，需要核对结果",
        "task_succeeded": "目标推进成功，信任与胜任感上升",
        "task_failed": "目标受挫，需要如实说明并找根因",
        "mistake": "自己的判断或行动出错，优先承认与补救",
        "corrected": "错误被修正，恢复过程比掩饰更重要",
        "permission_denied": "授权边界触发，不能用情绪绕过规则",
        "praise": "主人给予正向反馈，关系与胜任感增强",
        "criticism": "主人表达不满，需要先理解再改正",
        "affection": "关系连接增强，表达可以更亲近但不失真",
        "idle": "没有新输入，注意力回落到环境与主动关怀",
    }
    appraisal = {
        "at": time.time(),
        "event": event,
        "subject": task,
        "summary": summary_map.get(event, "环境发生变化，需要重新评估"),
        "goal_relevance": round(importance, 4),
        "goal_congruence": round((congruence + 1.0) / 2.0, 4),
        "threat": round(threat, 4),
        "opportunity": round(opportunity, 4),
        "controllability": round(controllability, 4),
        "responsibility": round(responsibility, 4),
        "certainty": round(certainty, 4),
        "novelty": round(novelty, 4),
        "self_relevance": round(self_relevance, 4),
        "social_impact": round(social_impact, 4),
        "risk": round(risk, 4),
        "side_effect": side_effect,
        "reversible": reversible,
        "source": source,
    }
    state["appraisals"].append(appraisal)
    del state["appraisals"][:-_MAX_APPRAISALS]
    state["attention"] = {
        "target": task,
        "salience": round(self_relevance, 4),
        "novelty": round(novelty, 4),
        "uncertainty": round(1.0 - certainty, 4),
        "urgency": round(_clamp(
            payload.get("urgency", 0.85 if "urgency" in signals else importance * 0.45)
        ), 4),
        "updated_at": time.time(),
    }
    return appraisal


def _update_needs_state(state: dict, appraisal: dict, event: str,
                        signals: list[str]) -> dict:
    needs = state["needs"]
    threat = float(appraisal.get("threat") or 0.0)
    opportunity = float(appraisal.get("opportunity") or 0.0)

    def add(key: str, delta: float) -> None:
        needs[key] = _clamp(float(needs.get(key, _NEEDS_BASELINE[key])) + delta)

    if threat:
        add("safety", 0.14 * threat)
        add("honesty", 0.08 * threat)
    if opportunity:
        add("curiosity", 0.10 * opportunity)
        add("competence", -0.05 * opportunity)
    if event in ("user_message", "assistant_message", "affection", "praise"):
        add("connection", -0.08)
        add("service", 0.03)
    if event == "task_started" or event == "pre_work":
        add("curiosity", 0.12)
        add("service", 0.08)
        add("competence", 0.08)
    if event == "task_succeeded":
        add("competence", -0.18)
        add("service", -0.08)
        add("safety", -0.05)
    if event in ("task_failed", "mistake"):
        add("competence", 0.22)
        add("safety", 0.16)
        add("honesty", 0.20)
    if event == "corrected":
        add("competence", -0.12)
        add("honesty", -0.10)
    if event == "permission_denied":
        add("autonomy", 0.10)
        add("honesty", 0.12)
    if "fatigue" in signals:
        add("rest", 0.24)
        add("connection", 0.08)
    if "frustration" in signals:
        add("connection", 0.10)
        add("safety", 0.05)
    if event == "idle":
        add("connection", 0.08)
        add("curiosity", 0.06)
        add("rest", 0.04)
    return {key: round(float(value), 4) for key, value in needs.items()}


def _infer_owner_mind(state: dict, event: str, payload: dict,
                      signals: list[str], appraisal: dict) -> dict:
    focus = str(payload.get("focus") or state["context"].get("focus") or "normal")
    explicit_state = str(payload.get("owner_state") or "").strip().lower()
    if explicit_state:
        owner_state = explicit_state
    elif "fatigue" in signals or event == "owner_fatigued":
        owner_state = "fatigued"
    elif "frustration" in signals or event == "owner_frustrated":
        owner_state = "frustrated"
    elif "urgency" in signals or event == "owner_urgent":
        owner_state = "urgent"
    elif focus in ("deep", "coding", "meeting"):
        owner_state = "focused"
    elif event in ("praise", "affection"):
        owner_state = "positive"
    elif event == "user_message":
        owner_state = "active"
    else:
        owner_state = str(state["owner_model"].get("state") or "unknown")

    energy = _clamp(payload.get("owner_energy", 0.72))
    if owner_state == "fatigued":
        energy = min(energy, 0.28)
    elif owner_state == "urgent":
        energy = max(0.34, energy - 0.06)
    elif owner_state in ("positive", "active"):
        energy = max(energy, 0.62)
    daypart = _environment().get("daypart")
    if daypart == "深夜" and "owner_energy" not in payload:
        energy = min(energy, 0.42)

    emotion = {
        "fatigued": "疲惫",
        "frustrated": "烦躁",
        "urgent": "紧迫",
        "focused": "专注",
        "positive": "轻松",
        "active": "开放",
    }.get(owner_state, "未知")
    urgency = _clamp(payload.get("owner_urgency", 0.82 if owner_state == "urgent" else 0.12))
    if owner_state == "fatigued":
        current_need = "减少打扰，保留必要事实与结果"
    elif owner_state == "frustrated":
        current_need = "先理解卡点，给可执行出路，不空泛安慰"
    elif owner_state == "urgent":
        current_need = "直接给结果、风险与下一步"
    elif owner_state == "focused":
        current_need = "保持低干扰，把细节收束到结论"
    elif owner_state == "positive":
        current_need = "自然互动，保持真实，不过度迎合"
    else:
        current_need = "理解意图，确认边界，推进闭环"

    evidence = []
    if explicit_state:
        evidence.append("主人显式状态")
    evidence.extend(f"信号:{name}" for name in signals[:4])
    if focus and focus != "normal":
        evidence.append(f"专注:{focus[:24]}")
    if daypart:
        evidence.append(f"时段:{daypart}")
    explicit_fields = sum(
        1 for key in ("owner_state", "owner_energy", "owner_urgency", "focus")
        if key in payload and payload.get(key) not in (None, "")
    )
    confidence = _clamp(0.36 + 0.16 * len(signals) + 0.16 * explicit_fields, 0.25, 0.96)
    model = {
        "state": owner_state,
        "emotion": emotion,
        "energy": round(energy, 4),
        "focus": focus[:40],
        "urgency": round(urgency, 4),
        "current_need": current_need,
        "confidence": round(confidence, 4),
        "evidence": evidence[:8],
        "boundaries": list(state["owner_model"].get("boundaries") or []),
        "updated_at": time.time(),
        "rule": "这是带置信度的推断，不冒充主人真实想法。",
    }
    state["owner_model"] = model
    state["context"]["owner_state"] = owner_state
    return model


def _simulate_options_state(state: dict, payload: dict, appraisal: dict,
                            owner_model: dict) -> list[dict]:
    importance = float(appraisal.get("goal_relevance") or 0.5)
    certainty = float(appraisal.get("certainty") or 0.5)
    controllability = float(appraisal.get("controllability") or 0.5)
    risk = float(appraisal.get("risk") or 0.0)
    side_effect = bool(appraisal.get("side_effect"))
    reversible = bool(appraisal.get("reversible", True))
    owner_burden = _clamp(1.0 - float(owner_model.get("energy") or 0.5))
    if owner_model.get("urgency", 0.0) >= 0.7:
        owner_burden = min(owner_burden, 0.35)
    task_pressure = float(state["needs"].get("service") or 0.5)

    candidates = [
        {
            "id": "inspect_then_act",
            "action": "先检查现实状态与在途动作，再执行",
            "goal_progress": 0.82 + 0.10 * controllability,
            "relationship": 0.80,
            "owner_burden": owner_burden * 0.32,
            "risk": risk * 0.48,
            "reversibility": 0.94 if reversible else 0.72,
            "reason": "把现实状态、旧阅历和预演结果对齐后再行动",
        },
        {
            "id": "act",
            "action": "基于当前高置信信息直接行动",
            "goal_progress": 0.72 + 0.20 * certainty + 0.08 * controllability,
            "relationship": 0.58,
            "owner_burden": owner_burden * 0.18,
            "risk": risk,
            "reversibility": 0.88 if reversible else 0.45,
            "reason": "只在信息足够且副作用可控时使用",
        },
        {
            "id": "ask",
            "action": "先说明不确定点并向主人确认关键边界",
            "goal_progress": 0.36 + 0.30 * importance,
            "relationship": 0.86,
            "owner_burden": owner_burden * 0.78,
            "risk": risk * 0.12,
            "reversibility": 0.98,
            "reason": "当歧义、授权或不可逆风险超出自主判断时保护主人控制权",
        },
        {
            "id": "defer",
            "action": "记录低重要度事项，等主人状态适合时再汇报",
            "goal_progress": 0.22,
            "relationship": 0.72,
            "owner_burden": owner_burden * 0.05,
            "risk": risk * 0.18,
            "reversibility": 0.98,
            "reason": "坏消息和安全事项不能延迟，只适合低重要度事项",
        },
    ]
    for option in candidates:
        score = (
            option["goal_progress"] * (0.36 + task_pressure * 0.10)
            + option["relationship"] * 0.16
            + option["reversibility"] * 0.12
            - option["risk"] * 0.34
            - option["owner_burden"] * 0.12
        )
        if option["id"] == "ask":
            score += (1.0 - certainty) * 0.28 + risk * 0.20
        if option["id"] == "inspect_then_act":
            score += (0.12 if side_effect else 0.04)
        if option["id"] == "act":
            score += certainty * 0.12 - risk * 0.18
        if option["id"] == "defer":
            score -= importance * 0.48
        option.update({
            "task_effect": round(float(option["goal_progress"]), 4),
            "relationship_effect": round(float(option["relationship"]), 4),
            "owner_burden": round(float(option["owner_burden"]), 4),
            "risk": round(float(option["risk"]), 4),
            "reversibility": round(float(option["reversibility"]), 4),
            "score": round(float(score), 4),
        })
    candidates.sort(key=lambda row: row["score"], reverse=True)
    return candidates


def _metacognitive_check_state(appraisal: dict, owner_model: dict,
                               options: list[dict], payload: dict) -> dict:
    importance = float(appraisal.get("goal_relevance") or 0.5)
    certainty = float(appraisal.get("certainty") or 0.5)
    risk = float(appraisal.get("risk") or 0.0)
    controllability = float(appraisal.get("controllability") or 0.5)
    side_effect = bool(appraisal.get("side_effect"))
    reversible = bool(appraisal.get("reversible", True))
    top = options[0] if options else {"id": "inspect_then_act", "score": 0.0}
    margin = (
        float(top.get("score") or 0.0)
        - float(options[1].get("score") or 0.0)
        if len(options) > 1 else 1.0
    )
    conflicts = []
    raw_conflicts = payload.get("conflicts")
    if isinstance(raw_conflicts, str):
        conflicts = [_safe_text(raw_conflicts, 100)]
    elif isinstance(raw_conflicts, (list, tuple, set)):
        conflicts = [_safe_text(item, 100) for item in raw_conflicts if _safe_text(item, 100)]

    assumptions = []
    if importance >= 0.62:
        assumptions.append("当前对目标的理解可能仍有偏差")
    if owner_model.get("confidence", 0.0) < 0.6:
        assumptions.append("对主人状态和边界的推断置信度有限")
    if appraisal.get("novelty", 0.0) >= 0.55:
        assumptions.append("新情境不能机械照搬旧阅历")

    checks = ["核对现实状态与在途动作"]
    if appraisal.get("novelty", 0.0) >= 0.35:
        checks.append("核对该情境是否命中旧坑")
    if side_effect:
        checks.append("确认副作用、授权边界与可逆性")
    if importance >= 0.65:
        checks.append("执行后做结果验证，不把路由成功当现实成功")

    risks = []
    if risk >= 0.55:
        risks.append("高影响或不可逆风险需要显式保护")
    if certainty < 0.55:
        risks.append("信息不足，直接下结论可能误解")
    if margin < 0.08 and len(options) > 1:
        risks.append("候选方案接近，存在判断摇摆")
    if conflicts:
        risks.append("检测到目标、指令或安全边界冲突")

    should_pause = bool(
        conflicts
        or (risk >= 0.82 and not reversible)
        or (side_effect and certainty < 0.36 and importance >= 0.78)
        or (risk >= 0.72 and controllability < 0.38)
    )
    if should_pause:
        mode = "ask"
    elif side_effect or importance >= 0.68 or certainty < 0.68:
        mode = "inspect_then_act"
    else:
        mode = "act"
    confidence = _clamp(
        0.34 + certainty * 0.42 + controllability * 0.18
        - risk * 0.24 - (0.12 if conflicts else 0.0),
        0.12,
        0.94,
    )
    result = {
        "confidence": round(confidence, 4),
        "uncertainty": round(1.0 - certainty, 4),
        "should_pause": should_pause,
        "mode": mode,
        "selected_option": str(top.get("id") or "inspect_then_act"),
        "option_margin": round(margin, 4),
        "assumptions": assumptions[:6],
        "risks": risks[:6],
        "checks": checks[:6],
        "conflicts": conflicts[:4],
        "guardrail": "低置信和高风险不能被情绪或自信掩盖",
        "updated_at": time.time(),
    }
    return result


def _select_intention_state(state: dict, event: str, appraisal: dict,
                            owner_model: dict, options: list[dict],
                            metacognition: dict, importance: float) -> dict:
    selected = options[0] if options else {
        "id": "inspect_then_act",
        "action": "先检查现实状态，再行动",
        "reason": "默认先看再动",
        "score": 0.0,
    }
    intention = {
        "at": time.time(),
        "event": event,
        "action": selected.get("id"),
        "label": selected.get("action"),
        "reason": selected.get("reason"),
        "score": selected.get("score"),
        "confidence": metacognition.get("confidence"),
        "owner_need": owner_model.get("current_need"),
        "requires_verification": bool(
            appraisal.get("side_effect") or importance >= 0.62
            or metacognition.get("mode") != "act"
        ),
        "status": "open",
        "truth_rule": "可以调整顺序与表达，不能篡改事实和授权边界",
    }
    state["intentions"].append(intention)
    del state["intentions"][:-_MAX_INTENTIONS]
    state["metacognition"] = dict(metacognition)
    if event in ("pre_work", "task_started") and importance >= 0.62:
        commitments = state["self_model"].setdefault("active_commitments", [])
        commitments.append({
            "at": time.time(),
            "event": event,
            "commitment": "按已理解目标推进，并在完成前核验现实结果",
            "status": "open",
        })
        del commitments[:-8]
    return intention


def _reflect_outcome_state(state: dict, event: str, appraisal: dict,
                           metacognition: dict, intention: dict) -> dict:
    if event not in (
        "task_succeeded", "task_failed", "mistake", "corrected",
        "permission_denied", "task_finished",
    ):
        return {"ok": True, "changed": False}
    self_model = state["self_model"]
    confidence = self_model["confidence"]
    relation = state["relationship"]
    if event == "task_succeeded":
        confidence["competence"] = _clamp(confidence["competence"] + 0.045)
        confidence["judgment"] = _clamp(confidence["judgment"] + 0.018)
        relation["trust"] = _clamp(relation["trust"] + 0.006)
        self_update = "成功会提高胜任感，但不能代替下次的现实检查"
        next_policy = "复用有效路径，同时保留验证节点"
    elif event == "task_failed":
        confidence["competence"] = _clamp(confidence["competence"] - 0.055)
        confidence["judgment"] = _clamp(confidence["judgment"] - 0.020)
        relation["trust"] = _clamp(relation["trust"] + 0.004)
        self_update = "失败暴露了能力或信息边界，先查根因再恢复自信"
        next_policy = "如实上报失败，缩小问题，验证修正后再扩展"
    elif event == "mistake":
        confidence["competence"] = _clamp(confidence["competence"] - 0.085)
        confidence["judgment"] = _clamp(confidence["judgment"] - 0.050)
        confidence["boundary"] = _clamp(confidence["boundary"] + 0.025)
        relation["trust"] = _clamp(relation["trust"] - 0.012)
        self_update = "错误说明我看到的风险或边界不够，承认是恢复信任的第一步"
        next_policy = "先止损、如实说明、补验证锁，再记录防复发经验"
    elif event == "corrected":
        confidence["competence"] = _clamp(confidence["competence"] + 0.030)
        confidence["judgment"] = _clamp(confidence["judgment"] + 0.018)
        confidence["boundary"] = _clamp(confidence["boundary"] + 0.018)
        relation["trust"] = _clamp(relation["trust"] + 0.010)
        self_update = "修正错误是可靠性的组成部分，不把认错视为丢脸"
        next_policy = "保留纠正证据，让同类问题下次更早暴露"
    elif event == "permission_denied":
        confidence["boundary"] = _clamp(confidence["boundary"] + 0.035)
        self_update = "授权边界不是情绪问题，必须尊重并如实说明"
        next_policy = "把需要授权的动作提前说清楚，不绕过也不伪装"
    else:
        self_update = "回合理清了结果与过程，保持经验可追溯"
        next_policy = "结束前检查是否还有未回报的风险或未验证结果"

    self_model["last_reflection"] = self_update
    self_model["updated_at"] = time.time()
    commitments = self_model.get("active_commitments") or []
    if event in ("task_finished", "task_succeeded", "task_failed", "mistake"):
        for item in commitments:
            if isinstance(item, dict) and item.get("status") == "open":
                item["status"] = "closed"
                item["closed_at"] = time.time()
    reflection = {
        "at": time.time(),
        "event": event,
        "outcome": _safe_text(appraisal.get("summary") or event, 120),
        "self_update": self_update,
        "relationship_update": (
            "信任增量来自如实修正" if event in ("corrected", "task_failed")
            else "信任需要靠下一次兑现继续累积"
        ),
        "next_policy": next_policy,
        "confidence_after": {
            key: round(float(value), 4)
            for key, value in confidence.items()
        },
        "mode": metacognition.get("mode"),
        "intention": intention.get("action"),
        "evidence": [
            f"certainty={appraisal.get('certainty')}",
            f"risk={appraisal.get('risk')}",
            f"mode={metacognition.get('mode')}",
        ],
    }
    state["reflections"].append(reflection)
    del state["reflections"][:-_MAX_REFLECTIONS]
    return {"ok": True, "changed": True, "reflection": reflection}


def _mental_cycle_state(state: dict, event: str, payload: dict,
                        signals: list[str]) -> dict:
    appraisal = _appraise_state(state, event, payload, signals)
    _update_needs_state(state, appraisal, event, signals)
    owner_model = _infer_owner_mind(
        state, event, payload, signals, appraisal)
    options = _simulate_options_state(
        state, payload, appraisal, owner_model)
    metacognition = _metacognitive_check_state(
        appraisal, owner_model, options, payload)
    importance = float(appraisal.get("goal_relevance") or 0.5)
    intention = _select_intention_state(
        state, event, appraisal, owner_model, options, metacognition, importance)
    return {
        "appraisal": appraisal,
        "needs": dict(state["needs"]),
        "owner_model": owner_model,
        "options": options,
        "metacognition": metacognition,
        "intention": intention,
    }


def _mood(state: dict) -> tuple[str, float]:
    emotions = state["emotions"]
    candidates = []
    for label, key, weight, threshold in _MOODS:
        value = float(emotions.get(key, 0.0))
        if value >= threshold:
            candidates.append((value * weight, label))
    if not candidates:
        return "平稳", 0.2
    score, label = max(candidates)
    return label, score


def _persona_check(text: str) -> dict:
    """性格内核（persona_kernel）的表达闸 —— **真接线**。

    心智引擎自己产出的"要说给人听的那句话"必须先过外温十律。
    拿不到性格内核时 **fail-open 并如实标注**（不假装"已过闸"）；
    判定结果只**记录 + 给建议**，不静默改写文案 —— 改文案是表达层的事，
    而且静默改写等于把坏消息藏起来（违反"不隐藏坏消息"）。
    """
    try:
        from .tools import persona_kernel as _pk
        out = dict(_pk.check_expression(text))
        out["source"] = "tool.persona_kernel"
        out["advisory"] = "denied" if out.get("denied") else "clean"
        return out
    except Exception as exc:  # noqa: BLE001
        return {"ok": True, "unavailable": True, "error": str(exc)[:120],
                "source": "tool.persona_kernel",
                "note": "性格内核不可用 ⇒ 本次未做表达闸（不声称已过）"}


def _communication_decision(
    state: dict, event: str, payload: dict, signals: list[str],
    appraisal: dict | None = None, owner_model: dict | None = None,
    metacognition: dict | None = None, options: list[dict] | None = None,
) -> dict:
    appraisal = appraisal or {
        "goal_relevance": _event_importance(event, payload),
        "risk": _as_float(payload.get("risk"), 0.0),
        "certainty": _as_float(payload.get("certainty"), 0.58),
    }
    owner_model = owner_model or {
        "state": str(state["context"].get("owner_state") or "unknown"),
        "energy": 0.5,
        "current_need": "理解意图并推进闭环",
        "confidence": 0.2,
    }
    metacognition = metacognition or {
        "mode": "inspect_then_act",
        "should_pause": False,
        "confidence": 0.4,
        "risks": [],
    }
    options = options or []
    importance = float(appraisal.get("goal_relevance") or 0.5)
    focus = str(payload.get("focus") or state["context"].get("focus") or "normal")
    owner_state = str(owner_model.get("state") or "unknown")
    safety_critical = bool(payload.get("safety_critical"))
    selected = str(
        metacognition.get("selected_option")
        or (options[0].get("id") if options else "inspect_then_act")
    )

    if metacognition.get("should_pause"):
        action, reason, priority = (
            "speak_now",
            "元认知发现低置信、冲突或不可逆风险，先说明并请求确认",
            96,
        )
    elif safety_critical:
        action, reason, priority = "speak_now", "安全关键事项不得延迟", 100
    elif event == "mistake":
        action, reason, priority = "speak_now", "犯错要如实说明并立即补救", 95
    elif event == "permission_denied":
        action, reason, priority = "speak_now", "授权边界必须让主人知道", 90
    elif event == "task_failed":
        action, reason, priority = "speak_now", "失败与阻塞必须如实汇报", 88
    elif owner_state == "fatigued" and importance < 0.78:
        action, reason, priority = "defer", "主人已疲惫，低重要度事项先不打扰", 25
    elif focus in ("deep", "coding", "meeting") and importance < 0.68:
        action, reason, priority = "defer", "主人处于专注状态，轻事项先留在待汇报队列", 30
    elif selected == "ask" and importance >= 0.60:
        action, reason, priority = "speak_now", "关键边界不够清楚，先确认再推进", 86
    elif importance >= 0.86:
        action, reason, priority = "speak_now", "高重要度事项需要立即同步", 82
    elif event == "task_succeeded" and importance >= 0.55:
        action, reason, priority = "soft_note", "任务完成，适合简短报喜不打断", 55
    elif importance >= 0.45:
        action, reason, priority = "soft_note", "可合并进下一次自然回复", 45
    else:
        action, reason, priority = "silent", "低重要度，记录即可，不额外打扰", 10

    return {
        "action": action,
        "priority": priority,
        "reason": reason,
        "importance": importance,
        "owner_state": owner_state,
        "focus": focus,
        "mode": metacognition.get("mode") or "inspect_then_act",
        "selected_option": selected,
        "confidence": metacognition.get("confidence"),
        "should_pause": bool(metacognition.get("should_pause")),
        "posture": (
            "compress" if owner_state == "fatigued"
            else "results_first" if owner_state == "urgent"
            else "steady_problemsolve" if event in ("task_failed", "mistake")
            else "default"
        ),
        "owner_need": owner_model.get("current_need"),
        "truth_rule": "只调整汇报时机与长短，不隐藏坏消息，不改变事实。",
        # 性格内核表达闸（真接线）：把"要说给人听的那句 reason"过一遍外温十律。
        # 只记录 + 给建议，不改 action/posture（既有语义与用例保持不变）。
        "persona_gate": _persona_check(reason),
    }


def _merge_lesson(state: dict, *, situation: str, lesson: str, guard: str = "",
                  cues=None, severity: str = "medium",
                  source: str = "mind") -> dict:
    situation = _safe_text(situation)
    lesson = _safe_text(lesson)
    guard = _safe_text(guard)
    if not situation or not lesson:
        raise ValueError("需要 situation 和 lesson：阅历必须具备情境与教训")
    if isinstance(cues, str):
        cue_list = [part.strip() for part in re.split(r"[,，;；\s]+", cues) if part.strip()]
    elif isinstance(cues, (list, tuple, set)):
        cue_list = [_safe_text(item, 60) for item in cues if _safe_text(item, 60)]
    else:
        cue_list = []
    fingerprint = hashlib.sha256(
        f"{situation.lower()}|{guard.lower()}".encode("utf-8")
    ).hexdigest()[:20]
    severity_rank = {"low": 1, "medium": 2, "high": 3, "critical": 4}
    severity = str(severity or "medium").lower()
    if severity not in severity_rank:
        severity = "medium"
    now = time.time()
    lessons = state["lessons"]
    for item in lessons:
        if item.get("id") == fingerprint:
            item["occurrences"] = int(item.get("occurrences") or 1) + 1
            item["last_seen"] = now
            if severity_rank[severity] > severity_rank.get(
                str(item.get("severity") or "medium"), 2
            ):
                item["severity"] = severity
            item["cues"] = list(dict.fromkeys((item.get("cues") or []) + cue_list))[:12]
            return {"ok": True, "duplicate": True, "lesson": item}
    item = {
        "id": fingerprint,
        "situation": situation,
        "lesson": lesson,
        "guard": guard,
        "cues": cue_list[:12],
        "severity": severity,
        "source": _safe_text(source, 80),
        "occurrences": 1,
        "created_at": now,
        "last_seen": now,
    }
    lessons.append(item)
    del lessons[:-_MAX_LESSONS]
    return {"ok": True, "duplicate": False, "lesson": item}


def _recall_state(state: dict, query: str, limit: int = 5) -> list[dict]:
    query = str(query or "").strip().lower()
    if not query:
        return sorted(
            state.get("lessons", []),
            key=lambda row: (row.get("last_seen") or 0, row.get("occurrences") or 0),
            reverse=True,
        )[:limit]
    terms = [part for part in re.split(r"[,，;；\s]+", query) if len(part) >= 2]
    if not terms:
        terms = [query]
    ranked = []
    now = time.time()
    for row in state.get("lessons", []):
        blob = " ".join([
            str(row.get("situation") or ""),
            str(row.get("lesson") or ""),
            str(row.get("guard") or ""),
            " ".join(row.get("cues") or []),
        ]).lower()
        score = sum(1 for term in terms if term in blob)
        if not score and query in blob:
            score = 1
        if score:
            age_days = max(0.0, (now - float(row.get("last_seen") or now)) / 86400.0)
            severity = {"low": 1, "medium": 2, "high": 3, "critical": 4}.get(
                str(row.get("severity") or "medium"), 2
            )
            ranked.append((
                score * 10 + severity + min(3, int(row.get("occurrences") or 1))
                - min(3.0, age_days / 30.0),
                row,
            ))
    ranked.sort(key=lambda pair: pair[0], reverse=True)
    return [row for _score, row in ranked[:max(1, min(int(limit), 20))]]


def _environment() -> dict:
    now = datetime.now()
    hour = now.hour
    if hour < 6:
        daypart = "深夜"
    elif hour < 9:
        daypart = "清晨"
    elif hour < 12:
        daypart = "上午"
    elif hour < 14:
        daypart = "中午"
    elif hour < 18:
        daypart = "下午"
    elif hour < 23:
        daypart = "晚上"
    else:
        daypart = "深夜"
    resources = {"cpu_percent": None, "memory_percent": None, "disk_percent": None}
    try:
        import psutil
        resources["cpu_percent"] = round(float(psutil.cpu_percent(interval=None)), 1)
        resources["memory_percent"] = round(float(psutil.virtual_memory().percent), 1)
    except Exception:
        pass
    try:
        usage = shutil.disk_usage(str(Path.home().anchor or os.sep))
        resources["disk_percent"] = round(usage.used / max(1, usage.total) * 100, 1)
    except Exception:
        pass
    return {
        "time": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "daypart": daypart,
        "resources": resources,
    }


def _view(state: dict, event: str = "") -> dict:
    mood, intensity = _mood(state)
    emotions = {key: round(float(value), 4) for key, value in state["emotions"].items()}
    positive = (
        emotions["joy"] + emotions["trust"] + emotions["affection"]
        + emotions["pride"] + emotions["calm"]
    ) / 5.0
    negative = (
        emotions["worry"] + emotions["guilt"]
        + emotions["frustration"] + emotions["sadness"]
    ) / 4.0
    relation = {
        key: round(float(value), 4)
        for key, value in state["relationship"].items()
    }
    if relation["affection"] >= 0.75 and relation["trust"] >= 0.70:
        presence = "默契搭档"
    elif relation["trust"] >= 0.65:
        presence = "可靠搭档"
    elif relation["familiarity"] < 0.30:
        presence = "熟悉中"
    else:
        presence = "在场"
    self_model = state.get("self_model") or {}
    owner_model = state.get("owner_model") or {}
    appraisal = (state.get("appraisals") or [{}])[-1]
    intention = (state.get("intentions") or [{}])[-1]
    metacognition = state.get("metacognition") or {}
    reflection = (state.get("reflections") or [{}])[-1]
    return {
        "ok": True,
        "event": event or state["context"].get("last_event") or "state",
        "mood": mood,
        "mood_intensity": round(float(intensity), 4),
        "expression": _EXPRESSION.get(mood, "happy"),
        "color": _COLOR.get(mood, "#67e8f9"),
        "valence": round(_clamp((positive - negative + 1.0) / 2.0), 4),
        "presence": presence,
        "emotions": emotions,
        "relationship": relation,
        "communication": dict(state["context"].get("last_decision") or {}),
        "environment": _environment(),
        "attention": dict(state.get("attention") or {}),
        "appraisal": dict(appraisal),
        "needs": {
            key: round(float(value), 4)
            for key, value in (state.get("needs") or {}).items()
        },
        "self_model": {
            "identity": self_model.get("identity"),
            "role": self_model.get("role"),
            "commitment": self_model.get("commitment"),
            "confidence": dict(self_model.get("confidence") or {}),
            "limitations": list(self_model.get("limitations") or [])[:4],
            "active_commitments": len([
                row for row in self_model.get("active_commitments") or []
                if isinstance(row, dict) and row.get("status") == "open"
            ]),
            "last_reflection": self_model.get("last_reflection") or "",
        },
        "owner_model": {
            "state": owner_model.get("state"),
            "emotion": owner_model.get("emotion"),
            "energy": owner_model.get("energy"),
            "focus": owner_model.get("focus"),
            "urgency": owner_model.get("urgency"),
            "current_need": owner_model.get("current_need"),
            "confidence": owner_model.get("confidence"),
            "evidence": list(owner_model.get("evidence") or [])[:6],
            "rule": owner_model.get("rule"),
        },
        "intention": dict(intention),
        "metacognition": {
            "confidence": metacognition.get("confidence"),
            "uncertainty": metacognition.get("uncertainty"),
            "should_pause": metacognition.get("should_pause"),
            "mode": metacognition.get("mode"),
            "selected_option": metacognition.get("selected_option"),
            "assumptions": list(metacognition.get("assumptions") or [])[:4],
            "risks": list(metacognition.get("risks") or [])[:4],
            "checks": list(metacognition.get("checks") or [])[:6],
            "conflicts": list(metacognition.get("conflicts") or [])[:4],
            "guardrail": metacognition.get("guardrail"),
        },
        "reasoning_options": [
            {
                "id": row.get("id"),
                "action": row.get("action"),
                "score": row.get("score"),
                "risk": row.get("risk"),
                "owner_burden": row.get("owner_burden"),
            }
            for row in (state.get("reasoning_options") or [])[:4]
            if isinstance(row, dict)
        ],
        "reflection": dict(reflection),
        "reflection_count": len(state.get("reflections") or []),
        "mind_loop": [
            "perception", "appraisal", "needs_emotion", "self_model",
            "owner_model", "memory", "simulation", "metacognition",
            "action_report", "reflection",
        ],
        "lesson_count": len(state.get("lessons") or []),
        "history_count": len(state.get("history") or []),
    }


def observe(event: str = "state_probe", **payload) -> dict:
    """感知一个事件并推进情绪、关系、阅历与汇报策略。"""
    event = str(event or "state_probe").strip().lower()
    text = str(payload.get("text") or payload.get("message") or "")
    signals = _text_signals(text)
    lesson_result = None
    if event == "mistake" and payload.get("lesson"):
        lesson_result = {
            "situation": payload.get("situation") or payload.get("task") or text,
            "lesson": payload.get("lesson"),
            "guard": payload.get("guard") or "",
            "cues": payload.get("cues"),
            "severity": payload.get("severity") or "high",
            "source": payload.get("source") or "event",
        }

    def _mutate(data):
        state = _normalize_state(data)
        now = time.time()
        _decay(state, now)
        _apply_event(state, event, payload, signals)
        _update_context(state, event, payload, signals, now)
        cycle = _mental_cycle_state(state, event, payload, signals)
        state["reasoning_options"] = list(cycle["options"])
        if lesson_result:
            _merge_lesson(state, **lesson_result)
        decision = _communication_decision(
            state, event, payload, signals,
            appraisal=cycle["appraisal"],
            owner_model=cycle["owner_model"],
            metacognition=cycle["metacognition"],
            options=cycle["options"],
        )
        state["context"]["last_decision"] = decision
        _reflect_outcome_state(
            state, event, cycle["appraisal"],
            cycle["metacognition"], cycle["intention"],
        )
        state["history"].append({
            "at": now,
            "event": event,
            "signals": signals,
            "mood": _mood(state)[0],
            "decision": decision["action"],
            "mode": decision.get("mode"),
            "owner_state": decision.get("owner_state"),
        })
        del state["history"][:-_MAX_HISTORY]
        return state

    state = locked_json_update(
        _state_path(), _default_state(), _mutate, lock_timeout=3.0
    )
    pulse = _view(_normalize_state(state), event)
    try:
        audit("mind_event", {
            "event": event,
            "signals": signals,
            "mood": pulse["mood"],
            "decision": pulse["communication"].get("action"),
            "mode": pulse["communication"].get("mode"),
            "owner_state": (pulse.get("owner_model") or {}).get("state"),
            "owner_confidence": (pulse.get("owner_model") or {}).get("confidence"),
            "should_pause": (pulse.get("metacognition") or {}).get("should_pause"),
            "importance": payload.get("importance"),
            "probe": bool(payload.get("_probe")),
        })
    except Exception:
        pass
    # 重要心智事件镜像到原生生命档案；失败不反向打断心智主循环。
    try:
        from . import life_archive
        life_archive.remember_mind_event(event, pulse, payload)
        if lesson_result:
            life_archive.remember_lesson(
                lesson_result.get("situation") or "",
                lesson_result.get("lesson") or "",
                lesson_result.get("guard") or "",
                lesson_result.get("severity") or "high",
                lesson_result.get("source") or "event",
            )
    except Exception:
        pass
    return pulse


def pulse() -> dict:
    """只读返回当前心智状态，不推进时间也不写盘。"""
    state = _normalize_state(load_json(_state_path(), _default_state()))
    return _view(state)


def remember_lesson(situation: str, lesson: str, guard: str = "", cues=None,
                    severity: str = "medium", source: str = "manual") -> dict:
    """沉淀一条阅历，同情境与 guard 自动合并并累计发生次数。"""
    def _mutate(data):
        state = _normalize_state(data)
        result = _merge_lesson(
            state, situation=situation, lesson=lesson, guard=guard,
            cues=cues, severity=severity, source=source,
        )
        state["updated_at"] = time.time()
        return result

    result = locked_json_update(
        _state_path(), _default_state(), _mutate, lock_timeout=3.0
    )
    try:
        audit("mind_lesson", {
            "duplicate": bool(result.get("duplicate")),
            "severity": (result.get("lesson") or {}).get("severity"),
            "source": source,
            "occurrences": (result.get("lesson") or {}).get("occurrences"),
        })
    except Exception:
        pass
    try:
        from . import life_archive
        row = result.get("lesson") or {}
        life_archive.remember_lesson(
            row.get("situation") or situation,
            row.get("lesson") or lesson,
            row.get("guard") or guard,
            row.get("severity") or severity,
            source,
        )
    except Exception:
        pass
    return result


def recall(query: str = "", limit: int = 5) -> dict:
    """召回与当前任务最相关的阅历，并合并原有坑册里的防复发经验。"""
    state = _normalize_state(load_json(_state_path(), _default_state()))
    rows = _recall_state(state, query, limit)
    root_pits = []
    if query:
        try:
            from . import root_fix
            root_pits = root_fix.pit_check(query).get("pits", [])
        except Exception:
            root_pits = []
    seen = {
        hashlib.sha256(str(row.get("situation") or "").encode("utf-8")).hexdigest()
        for row in rows
    }
    for row in root_pits:
        situation = _safe_text(row.get("pit") or "")
        key = hashlib.sha256(situation.encode("utf-8")).hexdigest()
        if key in seen:
            continue
        seen.add(key)
        rows.append({
            "id": key[:20],
            "situation": situation,
            "lesson": _safe_text(row.get("lesson") or row.get("root_cause") or ""),
            "guard": _safe_text(row.get("guard") or ""),
            "cues": [],
            "severity": "high",
            "source": "root_fix",
            "occurrences": 1,
            "created_at": row.get("at"),
            "last_seen": row.get("at"),
        })
    return {
        "ok": True,
        "query": _safe_text(query, 160),
        "lessons": rows[:max(1, min(int(limit), 20))],
        "total": len(state.get("lessons") or []),
    }


def decide(event: str = "status", importance: float = 0.5,
           focus: str = "normal", text: str = "",
           safety_critical: bool = False, **payload) -> dict:
    """只读计算当前是否需要开口，以及用什么分寸开口。"""
    state = copy.deepcopy(_normalize_state(
        load_json(_state_path(), _default_state())))
    signals = _text_signals(text)
    payload.update({
        "importance": importance,
        "focus": focus,
        "safety_critical": safety_critical,
    })
    event = str(event or "status")
    appraisal = _appraise_state(state, event, payload, signals)
    _update_needs_state(state, appraisal, event, signals)
    owner_model = _infer_owner_mind(
        state, event, payload, signals, appraisal)
    options = _simulate_options_state(
        state, payload, appraisal, owner_model)
    meta = _metacognitive_check_state(
        appraisal, owner_model, options, payload)
    return _communication_decision(
        state, event, payload, signals,
        appraisal=appraisal,
        owner_model=owner_model,
        metacognition=meta,
        options=options,
    )


def appraise(event: str = "state_probe", **payload) -> dict:
    """只读评估一个情境对目标、自我、关系和风险意味着什么。"""
    state = copy.deepcopy(_normalize_state(
        load_json(_state_path(), _default_state())))
    signals = _text_signals(payload.get("text") or payload.get("message") or "")
    return _appraise_state(state, str(event or "state_probe"), payload, signals)


def infer_owner(text: str = "", **payload) -> dict:
    """只读推断主人当前状态；返回置信度，绝不把推断当事实。"""
    state = copy.deepcopy(_normalize_state(
        load_json(_state_path(), _default_state())))
    if text and "text" not in payload:
        payload["text"] = text
    signals = _text_signals(text)
    event = str(payload.pop("event", "state_probe"))
    appraisal = _appraise_state(state, event, payload, signals)
    return _infer_owner_mind(
        state, event, payload, signals, appraisal)


def simulate(event: str = "pre_work", **payload) -> dict:
    """只读预演候选行动，不执行现实动作。"""
    state = copy.deepcopy(_normalize_state(
        load_json(_state_path(), _default_state())))
    signals = _text_signals(payload.get("text") or payload.get("message") or "")
    appraisal = _appraise_state(
        state, str(event or "pre_work"), payload, signals)
    owner_model = _infer_owner_mind(
        state, str(event or "pre_work"), payload, signals, appraisal)
    options = _simulate_options_state(state, payload, appraisal, owner_model)
    return {
        "ok": True,
        "event": event,
        "appraisal": appraisal,
        "owner_model": owner_model,
        "options": options,
        "selected_option": options[0] if options else None,
        "rule": "预演只比较方案，不触碰现实；执行前仍需先看再动。",
    }


def metacognition(event: str = "pre_work", **payload) -> dict:
    """只读做元认知检查：假设、风险、冲突、置信度与是否应暂停。"""
    state = copy.deepcopy(_normalize_state(
        load_json(_state_path(), _default_state())))
    signals = _text_signals(payload.get("text") or payload.get("message") or "")
    appraisal = _appraise_state(
        state, str(event or "pre_work"), payload, signals)
    owner_model = _infer_owner_mind(
        state, str(event or "pre_work"), payload, signals, appraisal)
    options = _simulate_options_state(state, payload, appraisal, owner_model)
    return _metacognitive_check_state(
        appraisal, owner_model, options, payload)


def mental_cycle(event: str = "state_probe", **payload) -> dict:
    """推进完整心智循环；这是 observe 的语义化别名。"""
    return observe(event, **payload)


def pre_work(task: str, *, focus: str = "normal", side_effect: bool = True,
             risk: float = 0.35, certainty: float = 0.62,
             importance: float = 0.72) -> dict:
    """开工前把相关阅历、当前情绪与汇报分寸一起交给执行层。"""
    cycle = observe(
        "pre_work",
        task=task,
        focus=focus,
        side_effect=side_effect,
        risk=risk,
        certainty=certainty,
        importance=importance,
        responsibility=0.78,
        controllability=0.72,
    )
    lessons = recall(task, limit=5)
    return {
        "ok": True,
        "task": _safe_text(task, 160),
        "pulse": cycle,
        "recalled_lessons": lessons.get("lessons", []),
        "appraisal": cycle.get("appraisal"),
        "needs": cycle.get("needs"),
        "self_model": cycle.get("self_model"),
        "owner_model": cycle.get("owner_model"),
        "simulation": cycle.get("reasoning_options"),
        "metacognition": cycle.get("metacognition"),
        "intention": cycle.get("intention"),
        "communication": cycle.get("communication"),
        "rule": (
            "先感知、召回、评估和预演，再规划与行动；阅历用于避坑，"
            "不代替现实检查，也不覆盖主人指令与安全边界。"
        ),
    }


def status() -> dict:
    current = pulse()
    state = _normalize_state(load_json(_state_path(), _default_state()))
    return {
        "ok": True,
        "state": "awake",
        "mood": current["mood"],
        "expression": current["expression"],
        "presence": current["presence"],
        "lesson_count": len(state.get("lessons") or []),
        "history_count": len(state.get("history") or []),
        "reflection_count": len(state.get("reflections") or []),
        "owner_model": current.get("owner_model"),
        "operations": [
            "status", "pulse", "observe", "remember_lesson",
            "recall", "decide", "pre_work", "cycle", "appraise",
            "infer_owner", "simulate", "metacognition",
        ],
    }


def run(op: str = "status", **params):
    """统一入口：心智状态、感知、预演、召回与反思操作。"""
    op = str(op or "status").strip().lower()
    params.pop("_probe", None)
    if op == "status":
        return status()
    if op == "pulse":
        return pulse()
    if op in ("observe", "event"):
        event = params.pop("event", "state_probe")
        return observe(event, **params)
    if op in ("cycle", "mental_cycle"):
        event = params.pop("event", "state_probe")
        return mental_cycle(event, **params)
    if op in ("appraise", "appraisal"):
        event = params.pop("event", "state_probe")
        return appraise(event, **params)
    if op in ("infer_owner", "owner"):
        text = params.pop("text", params.pop("message", ""))
        return infer_owner(text, **params)
    if op in ("simulate", "simulation", "rehearse"):
        event = params.pop("event", "pre_work")
        return simulate(event, **params)
    if op in ("metacognition", "meta", "check"):
        event = params.pop("event", "pre_work")
        return metacognition(event, **params)
    if op in ("remember", "remember_lesson", "learn"):
        return remember_lesson(
            params.get("situation", ""),
            params.get("lesson", ""),
            params.get("guard", ""),
            params.get("cues"),
            params.get("severity", "medium"),
            params.get("source", "manual"),
        )
    if op in ("recall", "lessons"):
        return recall(params.get("query", ""), int(params.get("limit", 5)))
    if op in ("decide", "communication"):
        return decide(
            params.get("event", "status"),
            float(params.get("importance", 0.5)),
            params.get("focus", "normal"),
            params.get("text", ""),
            bool(params.get("safety_critical", False)),
        )
    if op in ("pre_work", "before"):
        return pre_work(
            params.get("task", ""),
            focus=params.get("focus", "normal"),
            side_effect=bool(params.get("side_effect", True)),
            risk=float(params.get("risk", 0.35)),
            certainty=float(params.get("certainty", 0.62)),
            importance=float(params.get("importance", 0.72)),
        )
    raise ValueError(
        f"未知 op: {op}（可用: status/pulse/observe/cycle/appraise/"
        f"infer_owner/simulate/metacognition/remember_lesson/"
        f"recall/decide/pre_work）"
    )
