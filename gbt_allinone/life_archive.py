"""GBT小土豆V8 · 原生生命档案与时光轨迹。

这里不是外部笔记软件的附属层，也不是把完整聊天塞进数据库。它是一套可审计、
可召回、可反思、可迁移的原生生命时间线：

  事件 -> 每日 -> 章节 -> 关系/项目 -> 承诺/习惯 -> 阅历 -> 反思
       -> Obsidian 兼容镜像

主数据保存在框架自己的 ``store/life/events.jsonl``。Markdown Vault 只是可读、
可迁移、可由 Obsidian 打开的镜像，不是小土豆的身份或记忆后端。

隐私边界：
  - 只保存短摘要、结构化标签、数值、置信度、关系与经验；
  - 不保存完整对话、完整提示词、原始图片、原始音频或密钥；
  - 所有自由文本先经过统一脱敏与长度限制；
  - 导出 Markdown 前仍沿用同一最小化数据，不扩大可见面。
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from . import _paths
from .safe_io import (
    FileLock,
    atomic_write_json,
    atomic_write_text,
    load_json,
    locked_append_text,
    locked_json_update,
)
from .security.data_policy import redact_text
from .store import audit

_SCHEMA_VERSION = 1
_MAX_TEXT = 500
_MAX_TITLE = 160
_DEDUPE_SCAN = 2000

_CAPTURE_MIND_EVENTS = {
    "pre_work",
    "task_started",
    "task_finished",
    "task_succeeded",
    "task_failed",
    "mistake",
    "corrected",
    "permission_denied",
    "praise",
    "criticism",
    "affection",
    "startup_ready",
    "relationship_change",
    "commitment",
    "habit",
    "chapter",
}

_EVENT_TITLES = {
    "pre_work": "开始一项重要工作",
    "task_started": "任务开始",
    "task_finished": "任务收束",
    "task_succeeded": "任务完成",
    "task_failed": "任务失败",
    "mistake": "发生一次失误",
    "corrected": "错误已纠正",
    "permission_denied": "授权边界被触发",
    "praise": "获得认可",
    "criticism": "收到批评",
    "affection": "关系互动",
    "startup_ready": "意识重新上线",
}

_TYPE_ALIASES = {
    "success": "milestone",
    "succeeded": "milestone",
    "done": "milestone",
    "failure": "lesson",
    "failed": "lesson",
    "error": "lesson",
    "reflection": "reflection",
    "insight": "lesson",
    "relationship_change": "relationship",
    "person": "relationship",
    "task_started": "task",
    "task_finished": "task",
    "pre_work": "task",
}


def _now() -> datetime:
    return datetime.now().astimezone()


def _aware(value: datetime) -> datetime:
    """给历史导入的无时区时间补上当前本地时区，保持旧数据可比较。"""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=_now().tzinfo)
    return value


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat(timespec="seconds")


def _store() -> Path:
    return Path(_paths.STORE_DIR)


def _life_dir() -> Path:
    return _store() / "life"


def _event_path() -> Path:
    return _life_dir() / "events.jsonl"


def _state_path() -> Path:
    return _life_dir() / "state.json"


def _lock_path() -> Path:
    return _life_dir() / "life.lock"


def _default_vault() -> Path:
    return _store() / "life_vault"


def _clamp(value, low: float = 0.0, high: float = 1.0) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return low


def _safe_text(value, limit: int = _MAX_TEXT) -> str:
    text, _counts = redact_text(str(value or ""))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max(1, int(limit))]


def _safe_items(value, limit: int = 20, item_limit: int = 100) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set, frozenset)):
        return []
    items: list[str] = []
    for raw in value:
        text = _safe_text(raw, item_limit)
        if text and text not in items:
            items.append(text)
        if len(items) >= limit:
            break
    return items


def _event_type(value) -> str:
    text = _safe_text(value or "event", 48).lower()
    text = re.sub(r"[^a-z0-9_\-\u4e00-\u9fff]+", "_", text).strip("_")
    return _TYPE_ALIASES.get(text, text or "event")[:48]


def _slug(value, fallback: str = "item", limit: int = 72) -> str:
    text = _safe_text(value, limit * 2).strip()
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", text)
    text = re.sub(r"\s+", "_", text).strip("._ ")
    return (text or fallback)[:limit]


def _digest(value) -> str:
    if isinstance(value, bytes):
        body = value
    elif isinstance(value, str):
        body = value.encode("utf-8", errors="replace")
    else:
        body = json.dumps(
            value, ensure_ascii=False, sort_keys=True, default=str
        ).encode("utf-8", errors="replace")
    return hashlib.sha256(body).hexdigest()


def _new_id(prefix: str = "life") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def _parse_dt(value) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return _aware(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        for pattern in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                return _aware(datetime.strptime(text, pattern))
            except ValueError:
                continue
    return None


def _event_date(event: dict) -> str:
    parsed = _parse_dt(event.get("at"))
    return parsed.strftime("%Y-%m-%d") if parsed else ""


def _iter_events_reversed():
    path = _event_path()
    if not path.exists():
        return
    with open(path, "rb") as handle:
        handle.seek(0, 2)
        pos = handle.tell()
        buf = b""
        while pos > 0:
            step = min(65536, pos)
            pos -= step
            handle.seek(pos)
            buf = handle.read(step) + buf
            lines = buf.split(b"\n")
            buf = lines.pop(0)
            for raw in reversed(lines):
                if not raw.strip():
                    continue
                try:
                    row = json.loads(raw.decode("utf-8", errors="replace"))
                except Exception:
                    continue
                if isinstance(row, dict):
                    yield row
        if buf.strip():
            try:
                row = json.loads(buf.decode("utf-8", errors="replace"))
            except Exception:
                row = None
            if isinstance(row, dict):
                yield row


def _load_events(limit: int | None = None) -> list[dict]:
    rows = list(_iter_events_reversed())
    rows.reverse()
    if limit is not None:
        return rows[-max(0, int(limit)):]
    return rows


def _default_state() -> dict:
    now = _iso()
    return {
        "version": _SCHEMA_VERSION,
        "created_at": now,
        "updated_at": now,
        "last_event_at": None,
        "counts": {},
        "chapters": [],
        "commitments": [],
        "habits": [],
        "last_export": None,
    }


def _normalize_state(value) -> dict:
    state = value if isinstance(value, dict) else {}
    default = _default_state()
    for key, fallback in default.items():
        state.setdefault(key, fallback)
    if not isinstance(state.get("counts"), dict):
        state["counts"] = {}
    for key in ("chapters", "commitments", "habits"):
        if not isinstance(state.get(key), list):
            state[key] = []
    state["version"] = _SCHEMA_VERSION
    return state


def _source(value) -> dict:
    raw = value if isinstance(value, dict) else {}
    return {
        "kind": _safe_text(raw.get("kind") or "manual", 60),
        "ref": _safe_text(raw.get("ref") or "", 240),
        "digest": _safe_text(raw.get("digest") or "", 80),
    }


def _normalize_event(value: dict, *, event_id: str | None = None,
                    at: str | None = None) -> dict:
    raw = value if isinstance(value, dict) else {}
    title = _safe_text(raw.get("title") or raw.get("event") or "未命名事件",
                       _MAX_TITLE)
    summary = _safe_text(
        raw.get("summary") or raw.get("detail") or raw.get("description") or title
    )
    event_type = _event_type(raw.get("type") or raw.get("event_type") or "event")
    source = _source(raw.get("source"))
    explicit_id = _safe_text(event_id or raw.get("id") or "", 80)
    return {
        "schema": _SCHEMA_VERSION,
        "id": explicit_id or _new_id("evt"),
        "at": _iso(_parse_dt(at or raw.get("at") or raw.get("timestamp"))),
        "type": event_type,
        "title": title,
        "summary": summary,
        "importance": round(_clamp(raw.get("importance", 0.5)), 4),
        "confidence": round(_clamp(raw.get("confidence", 0.82)), 4),
        "valence": round(max(-1.0, min(1.0, _clamp(
            raw.get("valence", 0.0), -1.0, 1.0))), 4),
        "tags": _safe_items(raw.get("tags")),
        "people": _safe_items(raw.get("people")),
        "projects": _safe_items(raw.get("projects")),
        "capabilities": _safe_items(raw.get("capabilities")),
        "links": _safe_items(raw.get("links")),
        "source": source,
        "evidence_sha256": _safe_text(
            raw.get("evidence_sha256")
            or (_digest(raw.get("evidence")) if raw.get("evidence") is not None else ""),
            80,
        ),
        "privacy": _safe_text(raw.get("privacy") or "private", 32),
        "dedupe_key": _safe_text(raw.get("dedupe_key") or "", 160),
    }


def _event_summary(event: dict) -> dict:
    keys = (
        "id", "at", "type", "title", "summary", "importance", "confidence",
        "valence", "tags", "people", "projects", "capabilities", "links",
        "source", "evidence_sha256", "privacy",
    )
    return {key: event.get(key) for key in keys}


def _dedupe_matches(event: dict) -> bool:
    key = str(event.get("dedupe_key") or "").strip()
    source_ref = str((event.get("source") or {}).get("ref") or "").strip()
    if not key and not source_ref:
        return False
    scanned = 0
    for row in _iter_events_reversed():
        scanned += 1
        if scanned > _DEDUPE_SCAN:
            break
        if key and str(row.get("dedupe_key") or "") == key:
            return True
        if source_ref and str((row.get("source") or {}).get("ref") or "") == source_ref:
            return True
    return False


def _bump_state(event: dict) -> None:
    def _mutate(data):
        state = _normalize_state(data)
        state["updated_at"] = _iso()
        state["last_event_at"] = event.get("at")
        counts = state.setdefault("counts", {})
        event_type = str(event.get("type") or "event")
        counts[event_type] = int(counts.get(event_type) or 0) + 1
        return state

    locked_json_update(_state_path(), _default_state(), _mutate, lock_timeout=10)


def record_event(value: dict, *, event_id: str | None = None,
                 at: str | None = None) -> dict:
    """记录一个最小化生命事件；重复 source.ref/dedupe_key 幂等复用。"""
    event = _normalize_event(value, event_id=event_id, at=at)
    _life_dir().mkdir(parents=True, exist_ok=True)
    with FileLock(_lock_path(), timeout=15):
        if _dedupe_matches(event):
            return {"ok": True, "duplicate": True, "event": _event_summary(event)}
        locked_append_text(
            _event_path(),
            json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n",
            lock_timeout=10,
        )
        _bump_state(event)
    try:
        audit("life_event", {
            "id": event["id"],
            "type": event["type"],
            "importance": event["importance"],
            "source": event["source"].get("kind"),
            "tags": len(event["tags"]),
        })
    except Exception:
        pass
    return {"ok": True, "duplicate": False, "event": _event_summary(event)}


def _within(event: dict, start: str | None = None, end: str | None = None) -> bool:
    at = _parse_dt(event.get("at"))
    if at is None:
        return False
    if start:
        lhs = _parse_dt(start)
        if lhs is not None and at < lhs:
            return False
    if end:
        rhs = _parse_dt(end)
        if rhs is not None:
            if len(str(end)) <= 10:
                rhs = rhs + timedelta(days=1)
            if at >= rhs:
                return False
    return True


def timeline(*, start: str | None = None, end: str | None = None,
             event_type: str | None = None, tag: str | None = None,
             chapter: str | None = None, limit: int = 100,
             ascending: bool = True) -> dict:
    """只读时光轴；按时间、类型、标签或章节筛选。"""
    wanted_type = _event_type(event_type) if event_type else ""
    wanted_tag = _safe_text(tag, 80).lower() if tag else ""
    wanted_chapter = _safe_text(chapter, 80) if chapter else ""
    rows = []
    for event in _load_events():
        if not _within(event, start, end):
            continue
        if wanted_type and event.get("type") != wanted_type:
            continue
        if wanted_tag and wanted_tag not in {
            str(item).lower() for item in event.get("tags") or []
        }:
            continue
        if wanted_chapter and wanted_chapter not in {
            str(item) for item in event.get("links") or []
        } and str((event.get("source") or {}).get("ref") or "") != wanted_chapter:
            continue
        rows.append(_event_summary(event))
    rows.sort(key=lambda row: (
        _parse_dt(row.get("at")).timestamp()
        if _parse_dt(row.get("at")) is not None
        else float("-inf"),
        row.get("id") or "",
    ))
    if not ascending:
        rows.reverse()
    limit = max(1, min(int(limit), 1000))
    return {
        "ok": True,
        "total": len(rows),
        "events": rows[:limit],
        "order": "asc" if ascending else "desc",
    }


def build_daily(date: str | None = None) -> dict:
    """生成某一天的只读生命摘要。"""
    day = _safe_text(date, 10) if date else _now().strftime("%Y-%m-%d")
    events = [
        _event_summary(event)
        for event in _load_events()
        if _event_date(event) == day
    ]
    type_counts = Counter(str(row.get("type") or "event") for row in events)
    tags = Counter(
        str(tag)
        for row in events
        for tag in row.get("tags") or []
    )
    valences = [
        float(row.get("valence") or 0.0)
        for row in events
        if row.get("valence") is not None
    ]
    average_valence = sum(valences) / len(valences) if valences else 0.0
    if average_valence >= 0.35:
        tone = "明亮"
    elif average_valence <= -0.35:
        tone = "沉重"
    else:
        tone = "平稳"
    highlights = sorted(
        events,
        key=lambda row: (-float(row.get("importance") or 0.0), row.get("at") or ""),
    )[:5]
    return {
        "ok": True,
        "date": day,
        "count": len(events),
        "first_at": events[0].get("at") if events else None,
        "last_at": events[-1].get("at") if events else None,
        "type_counts": dict(type_counts),
        "top_tags": tags.most_common(12),
        "tone": tone,
        "average_valence": round(average_valence, 4),
        "highlights": highlights,
        "events": events,
    }


def recall(query: str = "", limit: int = 10) -> dict:
    """从生命档案召回相关事件，保留时间与来源，不制造不存在的事实。"""
    needle = _safe_text(query, 240).lower()
    rows = []
    for event in _load_events():
        haystacks = [
            str(event.get("title") or "").lower(),
            str(event.get("summary") or "").lower(),
            " ".join(event.get("tags") or []).lower(),
            " ".join(event.get("people") or []).lower(),
            " ".join(event.get("projects") or []).lower(),
            " ".join(event.get("capabilities") or []).lower(),
        ]
        if needle and not any(needle in item for item in haystacks):
            continue
        score = float(event.get("importance") or 0.0)
        if needle and needle in str(event.get("title") or "").lower():
            score += 1.5
        if needle and needle in str(event.get("summary") or "").lower():
            score += 0.8
        rows.append((score, event))
    rows.sort(
        key=lambda pair: (pair[0], pair[1].get("at") or ""),
        reverse=True,
    )
    result = [_event_summary(event) for _score, event in rows[:max(1, min(int(limit), 50))]]
    return {"ok": True, "query": _safe_text(query, 240), "count": len(result),
            "events": result}


def graph(limit_events: int = 1000) -> dict:
    """生成可迁移的关系图谱：事件、标签、人、项目、能力与链接。"""
    events = _load_events(limit=max(1, min(int(limit_events), 5000)))
    nodes: dict[str, dict] = {}
    edges: set[tuple[str, str, str]] = set()

    def add_node(node_id: str, label: str, kind: str) -> None:
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "label": _safe_text(label, 100), "kind": kind}

    for event in events:
        event_id = f"event:{event.get('id')}"
        add_node(event_id, str(event.get("title") or "event"), "event")
        for kind, field in (
            ("tag", "tags"),
            ("person", "people"),
            ("project", "projects"),
            ("capability", "capabilities"),
            ("link", "links"),
        ):
            for item in event.get(field) or []:
                node_id = f"{kind}:{_safe_text(item, 100).lower()}"
                add_node(node_id, str(item), kind)
                edges.add((event_id, node_id, kind))
    return {
        "ok": True,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": list(nodes.values()),
        "edges": [
            {"from": source, "to": target, "kind": kind}
            for source, target, kind in sorted(edges)
        ],
    }


def reflect(period: str = "week", *, save: bool = False,
            note: str = "") -> dict:
    """对一段时间做结构化反思；可选把反思本身写回生命档案。"""
    now = _now()
    period = str(period or "week").lower()
    if period in ("today", "day"):
        start = now.strftime("%Y-%m-%d")
    elif period in ("month", "30d"):
        start = (now - timedelta(days=30)).strftime("%Y-%m-%d")
    elif period in ("all", "life"):
        start = None
    else:
        start = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    events = [
        _event_summary(event)
        for event in _load_events()
        if start is None or _within(event, start, None)
    ]
    counts = Counter(str(row.get("type") or "event") for row in events)
    lessons = [
        row for row in events
        if row.get("type") in {"lesson", "mistake", "correction"}
        or "lesson" in (row.get("tags") or [])
    ][-10:]
    milestones = [
        row for row in events
        if row.get("type") in {"milestone", "commitment", "chapter"}
        or float(row.get("importance") or 0) >= 0.85
    ][-10:]
    state = _normalize_state(load_json(_state_path(), _default_state()))
    open_commitments = [
        row for row in state.get("commitments") or []
        if row.get("status") == "open"
    ]
    result = {
        "ok": True,
        "period": period,
        "start": start,
        "event_count": len(events),
        "type_counts": dict(counts),
        "milestones": milestones,
        "lessons": lessons,
        "open_commitments": open_commitments[:20],
        "habits": list(state.get("habits") or [])[:20],
        "note": _safe_text(note, 320),
    }
    if save:
        recorded = record_event({
            "type": "reflection",
            "title": f"{period} 反思",
            "summary": note or (
                f"回顾 {len(events)} 个事件，里程碑 {len(milestones)} 个，"
                f"阅历 {len(lessons)} 条，未完成承诺 {len(open_commitments)} 项。"
            ),
            "importance": 0.72,
            "tags": ["reflection", period],
            "source": {"kind": "life_archive.reflect", "ref": _digest(result)},
        })
        result["saved"] = recorded
    return result


def chapter(action: str = "list", **payload) -> dict:
    """人生章节：开启、更新、收束与回看。"""
    action = str(action or "list").lower()
    if action in ("list", "status"):
        state = _normalize_state(load_json(_state_path(), _default_state()))
        return {"ok": True, "chapters": state.get("chapters") or []}
    if action not in ("open", "close", "update"):
        raise ValueError("chapter action 必须是 open/close/update/list")
    if action == "open":
        title = _safe_text(payload.get("title") or "未命名章节", _MAX_TITLE)
        chapter_id = _safe_text(payload.get("id") or "", 80) or _new_id("chapter")
        row = {
            "id": chapter_id,
            "title": title,
            "summary": _safe_text(payload.get("summary") or "", _MAX_TEXT),
            "status": "open",
            "opened_at": _iso(),
            "closed_at": None,
            "tags": _safe_items(payload.get("tags")),
        }

        def _mutate(data):
            state = _normalize_state(data)
            if any(item.get("id") == chapter_id for item in state["chapters"]):
                return False
            state["chapters"].append(row)
            state["updated_at"] = _iso()
            return True

        created = locked_json_update(
            _state_path(), _default_state(), _mutate, lock_timeout=10)
        if created:
            record_event({
                "type": "chapter",
                "title": f"开启章节：{title}",
                "summary": row["summary"] or title,
                "importance": 0.9,
                "tags": ["chapter", *row["tags"]],
                "links": [f"Chapters/{title}"],
                "source": {"kind": "life_archive.chapter", "ref": chapter_id},
            })
        return {"ok": True, "created": created, "chapter": row}

    chapter_id = _safe_text(payload.get("id") or payload.get("chapter_id") or "", 80)
    title = _safe_text(payload.get("title") or "", _MAX_TITLE)
    if not chapter_id and not title:
        raise ValueError("close/update 需要 id 或 title")
    changed = {"row": None}

    def _mutate(data):
        state = _normalize_state(data)
        for row in state["chapters"]:
            if (chapter_id and row.get("id") == chapter_id) or (
                title and row.get("title") == title
            ):
                if action == "close":
                    row["status"] = "closed"
                    row["closed_at"] = _iso()
                if payload.get("summary") is not None:
                    row["summary"] = _safe_text(payload.get("summary"), _MAX_TEXT)
                if payload.get("tags") is not None:
                    row["tags"] = _safe_items(payload.get("tags"))
                state["updated_at"] = _iso()
                changed["row"] = dict(row)
                return True
        return False

    ok = locked_json_update(_state_path(), _default_state(), _mutate, lock_timeout=10)
    if ok and changed["row"]:
        row = changed["row"]
        record_event({
            "type": "chapter",
            "title": f"{'收束' if action == 'close' else '更新'}章节：{row['title']}",
            "summary": row.get("summary") or row["title"],
            "importance": 0.82,
            "tags": ["chapter", *(row.get("tags") or [])],
            "links": [f"Chapters/{row['title']}"],
            "source": {
                "kind": "life_archive.chapter",
                "ref": f"{row.get('id')}:{action}:{_digest(row)}",
            },
        })
    return {"ok": True, "updated": ok, "chapter": changed["row"]}


def commitment(action: str = "list", **payload) -> dict:
    """承诺账本：记住答应过什么，并在完成/放弃时留下轨迹。"""
    action = str(action or "list").lower()
    if action in ("list", "status"):
        state = _normalize_state(load_json(_state_path(), _default_state()))
        return {"ok": True, "commitments": state.get("commitments") or []}
    if action not in ("add", "update", "complete", "cancel", "reopen"):
        raise ValueError("commitment action 必须是 add/update/complete/cancel/reopen/list")
    if action == "add":
        title = _safe_text(payload.get("title") or "", _MAX_TITLE)
        if not title:
            raise ValueError("add 需要 title")
        row = {
            "id": _safe_text(payload.get("id") or "", 80) or _new_id("commit"),
            "title": title,
            "detail": _safe_text(payload.get("detail") or "", _MAX_TEXT),
            "status": "open",
            "created_at": _iso(),
            "updated_at": _iso(),
            "due_at": _safe_text(payload.get("due_at") or "", 40) or None,
            "importance": round(_clamp(payload.get("importance", 0.7)), 4),
            "tags": _safe_items(payload.get("tags")),
        }

        def _add(data):
            state = _normalize_state(data)
            if any(item.get("id") == row["id"] for item in state["commitments"]):
                return False
            state["commitments"].append(row)
            state["updated_at"] = _iso()
            return True

        created = locked_json_update(
            _state_path(), _default_state(), _add, lock_timeout=10)
        if created:
            record_event({
                "type": "commitment",
                "title": f"承诺：{title}",
                "summary": row["detail"] or title,
                "importance": row["importance"],
                "tags": ["commitment", "open", *row["tags"]],
                "source": {"kind": "life_archive.commitment", "ref": row["id"]},
            })
        return {"ok": True, "created": created, "commitment": row}

    target = _safe_text(payload.get("id") or payload.get("title") or "", 160)
    if not target:
        raise ValueError("需要 id 或 title")
    changed = {"row": None}
    status_map = {
        "complete": "done",
        "cancel": "cancelled",
        "reopen": "open",
        "update": None,
    }

    def _mutate(data):
        state = _normalize_state(data)
        for row in state["commitments"]:
            if row.get("id") != target and row.get("title") != target:
                continue
            new_status = status_map[action]
            if new_status:
                row["status"] = new_status
            if payload.get("detail") is not None:
                row["detail"] = _safe_text(payload.get("detail"), _MAX_TEXT)
            if payload.get("due_at") is not None:
                row["due_at"] = _safe_text(payload.get("due_at"), 40) or None
            if payload.get("importance") is not None:
                row["importance"] = round(_clamp(payload.get("importance")), 4)
            row["updated_at"] = _iso()
            changed["row"] = dict(row)
            state["updated_at"] = _iso()
            return True
        return False

    ok = locked_json_update(_state_path(), _default_state(), _mutate, lock_timeout=10)
    row = changed["row"]
    if ok and row:
        record_event({
            "type": "commitment",
            "title": f"承诺{row.get('status')}：{row.get('title')}",
            "summary": row.get("detail") or row.get("title") or "",
            "importance": row.get("importance") or 0.7,
            "tags": ["commitment", str(row.get("status") or "open")],
            "source": {
                "kind": "life_archive.commitment",
                "ref": f"{row.get('id')}:{action}:{_digest(row)}",
            },
        })
    return {"ok": True, "updated": ok, "commitment": row}


def habit(action: str = "list", **payload) -> dict:
    """习惯轨迹：定义、打卡、查看连续记录。"""
    action = str(action or "list").lower()
    if action in ("list", "status"):
        state = _normalize_state(load_json(_state_path(), _default_state()))
        return {"ok": True, "habits": state.get("habits") or []}
    if action not in ("define", "checkin"):
        raise ValueError("habit action 必须是 define/checkin/list")
    name = _safe_text(payload.get("name") or "", 100)
    if not name:
        raise ValueError("需要 name")
    if action == "define":
        row = {
            "id": _safe_text(payload.get("id") or "", 80) or _new_id("habit"),
            "name": name,
            "cadence": _safe_text(payload.get("cadence") or "daily", 40),
            "target": _safe_text(payload.get("target") or "", 120),
            "created_at": _iso(),
            "updated_at": _iso(),
            "last_checkin": None,
            "streak": 0,
            "total": 0,
        }

        def _define(data):
            state = _normalize_state(data)
            for current in state["habits"]:
                if current.get("name") == name or (
                    row["id"] and current.get("id") == row["id"]
                ):
                    return False
            state["habits"].append(row)
            state["updated_at"] = _iso()
            return True

        created = locked_json_update(
            _state_path(), _default_state(), _define, lock_timeout=10)
        if created:
            record_event({
                "type": "habit",
                "title": f"建立习惯：{name}",
                "summary": row["target"] or row["cadence"],
                "importance": 0.7,
                "tags": ["habit", row["cadence"]],
                "source": {"kind": "life_archive.habit", "ref": row["id"]},
            })
        return {"ok": True, "created": created, "habit": row}

    today = _now().strftime("%Y-%m-%d")
    result = {"row": None, "duplicate": False}

    def _checkin(data):
        state = _normalize_state(data)
        for row in state["habits"]:
            if row.get("name") != name and row.get("id") != name:
                continue
            previous = str(row.get("last_checkin") or "")
            if previous.startswith(today):
                result["row"] = dict(row)
                result["duplicate"] = True
                return False
            yesterday = (now_day - timedelta(days=1)).strftime("%Y-%m-%d")
            row["streak"] = int(row.get("streak") or 0) + 1 if previous.startswith(yesterday) else 1
            row["total"] = int(row.get("total") or 0) + 1
            row["last_checkin"] = _iso()
            row["updated_at"] = _iso()
            result["row"] = dict(row)
            state["updated_at"] = _iso()
            return True
        return False

    now_day = _now()
    ok = locked_json_update(_state_path(), _default_state(), _checkin, lock_timeout=10)
    if ok and result["row"]:
        row = result["row"]
        record_event({
            "type": "habit",
            "title": f"习惯打卡：{row['name']}",
            "summary": f"连续 {row.get('streak')} 次，累计 {row.get('total')} 次",
            "importance": 0.48,
            "tags": ["habit", str(row.get("cadence") or "daily")],
            "source": {
                "kind": "life_archive.habit",
                "ref": f"{row.get('id')}:{today}",
            },
        })
    return {"ok": True, "updated": ok, "duplicate": result["duplicate"],
            "habit": result["row"]}


def _yaml_string(value) -> str:
    return json.dumps(str(value or ""), ensure_ascii=False)


def _frontmatter(event: dict) -> str:
    lines = [
        "---",
        "gbt_generated: true",
        f'gbt_id: {_yaml_string(event.get("id"))}',
        f'gbt_type: {_yaml_string(event.get("type"))}',
        f'gbt_at: {_yaml_string(event.get("at"))}',
        f'gbt_importance: {float(event.get("importance") or 0):.4f}',
        f'gbt_confidence: {float(event.get("confidence") or 0):.4f}',
        f'gbt_valence: {float(event.get("valence") or 0):.4f}',
        "tags: " + json.dumps(event.get("tags") or [], ensure_ascii=False),
        "people: " + json.dumps(event.get("people") or [], ensure_ascii=False),
        "projects: " + json.dumps(event.get("projects") or [], ensure_ascii=False),
        "capabilities: " + json.dumps(
            event.get("capabilities") or [], ensure_ascii=False),
        "links: " + json.dumps(event.get("links") or [], ensure_ascii=False),
        "---",
    ]
    return "\n".join(lines)


def _event_note_rel(event: dict) -> str:
    at = _parse_dt(event.get("at")) or _now()
    slug = f"{at.strftime('%Y%m%d-%H%M%S')}-{_event_type(event.get('type'))}-{str(event.get('id'))[-8:]}"
    return f"Events/{at.strftime('%Y')}/{at.strftime('%m')}/{slug}.md"


def _event_note(event: dict) -> str:
    links = []
    for field in ("people", "projects", "capabilities", "links"):
        for item in event.get(field) or []:
            prefix = {
                "people": "People/",
                "projects": "Projects/",
                "capabilities": "Capabilities/",
                "links": "",
            }[field]
            links.append(f"- [[{prefix}{item}]]")
    source = event.get("source") or {}
    body = [
        _frontmatter(event),
        "",
        f"# {event.get('title')}",
        "",
        str(event.get("summary") or ""),
        "",
        "## 轨迹",
        "",
        f"- 时间：`{event.get('at')}`",
        f"- 类型：`{event.get('type')}`",
        f"- 重要度：`{event.get('importance')}`",
        f"- 置信度：`{event.get('confidence')}`",
        f"- 来源：`{source.get('kind') or 'manual'}`",
    ]
    if event.get("evidence_sha256"):
        body.append(f"- 证据指纹：`{event.get('evidence_sha256')}`")
    if links:
        body.extend(["", "## 关联", "", *links])
    return "\n".join(body).rstrip() + "\n"


def _daily_note(day: str, events: list[dict]) -> str:
    summary = build_daily(day)
    lines = [
        "---",
        "gbt_generated: true",
        f'gbt_date: {_yaml_string(day)}',
        f'gbt_events: {len(events)}',
        f'gbt_tone: {_yaml_string(summary.get("tone"))}',
        "---",
        "",
        f"# {day}",
        "",
        f"- 事件数：{len(events)}",
        f"- 时光气质：{summary.get('tone')}",
        f"- 平均情绪值：{summary.get('average_valence')}",
    ]
    if summary.get("top_tags"):
        lines.append("- 主题：" + "、".join(
            f"#{tag}" for tag, _count in summary["top_tags"][:8]))
    if summary.get("highlights"):
        lines.extend(["", "## 高光与转折", ""])
        for row in summary["highlights"]:
            note = _event_note_rel(_normalize_event(row))
            title = str(row.get("title") or "事件")
            lines.append(f"- [[{note[:-3]}|{title}]]")
    if events:
        lines.extend(["", "## 全天轨迹", ""])
        for event in events:
            note = _event_note_rel(event)
            parsed = _parse_dt(event.get("at"))
            clock = parsed.strftime("%H:%M") if parsed else "--:--"
            lines.append(
                f"- `{clock}` [[{note[:-3]}|{event.get('title')}]] "
                f"({event.get('type')})"
            )
    return "\n".join(lines).rstrip() + "\n"


def _index_page(title: str, rows: list[tuple[str, str]]) -> str:
    lines = [
        "---",
        "gbt_generated: true",
        f"gbt_index: {_yaml_string(title)}",
        "---",
        "",
        f"# {title}",
        "",
    ]
    lines.extend(f"- [[{target}|{label}]]" for target, label in rows)
    return "\n".join(lines).rstrip() + "\n"


def _write_generated(root: Path, files: dict[str, str],
                     *, force: bool = False) -> dict:
    manifest_path = root / ".gbt-life-manifest.json"
    previous = load_json(manifest_path, {}) or {}
    old_files = previous.get("files") if isinstance(previous.get("files"), dict) else {}
    next_files = dict(old_files)
    created, updated, unchanged, conflicts, backups = [], [], [], [], []
    for rel, content in sorted(files.items()):
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        incoming_hash = _digest(content)
        current_hash = _digest(target.read_bytes()) if target.exists() else ""
        conflict = False
        if target.exists():
            current_text = target.read_text(encoding="utf-8", errors="replace")
            owned = "gbt_generated: true" in current_text[:800]
            old_hash = old_files.get(rel)
            if not owned and old_hash is None:
                conflict = True
            elif old_hash is not None and current_hash != old_hash and current_hash != incoming_hash:
                conflict = True
        if conflict and not force:
            conflicts.append(rel)
            continue
        if conflict and force and target.exists():
            backup = target.with_name(
                target.name + f".backup-{time.strftime('%Y%m%d-%H%M%S')}")
            shutil.copy2(target, backup)
            backups.append(str(backup.relative_to(root)))
        if not target.exists():
            atomic_write_text(target, content)
            created.append(rel)
        elif current_hash != incoming_hash:
            atomic_write_text(target, content)
            updated.append(rel)
        else:
            unchanged.append(rel)
        next_files[rel] = incoming_hash
    atomic_write_json(manifest_path, {
        "version": 1,
        "updated_at": _iso(),
        "files": next_files,
    })
    return {
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "conflicts": conflicts,
        "backups": backups,
    }


def export_obsidian(vault: str | Path | None = None, *,
                    force: bool = False) -> dict:
    """导出 Obsidian 兼容 Vault；不覆盖未被本模块管理的用户文件。"""
    root = Path(vault).expanduser().resolve() if vault else _default_vault()
    events = _load_events()
    event_notes = {event["id"]: _event_note_rel(event) for event in events}
    by_day: dict[str, list[dict]] = defaultdict(list)
    people: dict[str, list[dict]] = defaultdict(list)
    projects: dict[str, list[dict]] = defaultdict(list)
    capabilities: dict[str, list[dict]] = defaultdict(list)
    lessons: list[dict] = []
    chapters: list[dict] = []
    for event in events:
        by_day[_event_date(event)].append(event)
        for person in event.get("people") or []:
            people[str(person)].append(event)
        for project in event.get("projects") or []:
            projects[str(project)].append(event)
        for capability in event.get("capabilities") or []:
            capabilities[str(capability)].append(event)
        if event.get("type") in {"lesson", "mistake", "correction", "reflection"}:
            lessons.append(event)
        if event.get("type") == "chapter":
            chapters.append(event)

    files: dict[str, str] = {
        "README.md": (
            "---\n"
            "gbt_generated: true\n"
            "---\n\n"
            "# GBT小土豆V8 · Life Vault\n\n"
            "这是小土豆原生生命档案的 Obsidian 兼容镜像。源数据在框架内部，"
            "本目录可读、可迁移、可用 Obsidian 打开。\n\n"
            "- [[Timeline]]\n"
            "- [[00_Meta/Identity]]\n"
            "- [[00_Meta/Commitments]]\n"
            "- [[00_Meta/Habits]]\n"
            "- [[Lessons/Index]]\n"
        ),
    }

    mind = {}
    mind_defaults = {}
    try:
        from . import mind_engine
        mind = mind_engine.pulse()
        mind_defaults = getattr(mind_engine, "_SELF_VALUES", {})
    except Exception:
        mind = {}
    raw_mind = load_json(_store() / "mind_state.json", {}) or {}
    self_model = raw_mind.get("self_model") or mind.get("self_model") or {}
    identity = self_model.get("identity") or "GBT小土豆V8"
    role = self_model.get("role") or "主人的数字人搭档与执行内核"
    commitment = self_model.get("commitment") or "忠于事实、主人指令和安全边界"
    files["00_Meta/Identity.md"] = _index_page(
        "Identity",
        [
            ("Timeline", "生命时间线"),
            ("00_Meta/Values", "价值与边界"),
            ("00_Meta/Commitments", "承诺账本"),
            ("00_Meta/Habits", "习惯轨迹"),
        ],
    ) + (
        "\n## Core\n\n"
        f"- 身份：{identity}\n"
        f"- 角色：{role}\n"
        f"- 承诺：{commitment}\n"
        f"- 最近反思：{self_model.get('last_reflection') or '暂无'}\n"
    )
    values = self_model.get("values") or mind_defaults
    limitations = self_model.get("limitations") or []
    value_lines = [
        f"- {name}：{round(float(score) * 100)}%"
        for name, score in values.items()
    ]
    files["00_Meta/Values.md"] = _index_page("Values", []) + (
        "\n## Values\n\n" + "\n".join(value_lines)
        + "\n\n## Limits\n\n"
        + "\n".join(f"- {item}" for item in limitations)
        + "\n"
    )

    state = _normalize_state(load_json(_state_path(), _default_state()))
    event_refs: dict[str, str] = {}
    for event in events:
        ref = str((event.get("source") or {}).get("ref") or "")
        if ref and ref not in event_refs:
            event_refs[ref] = event_notes[event["id"]][:-3]
    commitment_rows = [
        (
            event_refs.get(
                str(row.get("id") or ""),
                event_refs.get(
                    next((
                        ref for ref in event_refs
                        if ref.startswith(str(row.get("id") or "") + ":")
                    ), ""),
                    "",
                ),
            ),
            f"{row.get('title')} · {row.get('status')}",
        )
        for row in state.get("commitments") or []
    ]
    habit_rows = [
        (
            event_refs.get(
                next((
                    ref for ref in event_refs
                    if ref.startswith(str(row.get("id") or "") + ":")
                ), ""),
                "",
            ),
            f"{row.get('name')} · streak {row.get('streak', 0)}",
        )
        for row in state.get("habits") or []
    ]
    files["00_Meta/Commitments.md"] = _index_page(
        "Commitments", [row for row in commitment_rows if row[0]])
    files["00_Meta/Habits.md"] = _index_page(
        "Habits", [row for row in habit_rows if row[0]])

    timeline_rows = [
        (event_notes[event["id"]][:-3],
         f"{event.get('at')} · {event.get('title')}")
        for event in events[-200:]
    ]
    files["Timeline.md"] = _index_page("Timeline", timeline_rows)

    for event in events:
        files[event_notes[event["id"]]] = _event_note(event)
    for day, rows in by_day.items():
        if day:
            files[f"Daily/{day}.md"] = _daily_note(day, rows)

    for label, mapping, folder in (
        ("People", people, "People"),
        ("Projects", projects, "Projects"),
        ("Capabilities", capabilities, "Capabilities"),
    ):
        index_rows = []
        for name, rows in mapping.items():
            rel = f"{folder}/{_slug(name)}.md"
            index_rows.append((rel[:-3], name))
            event_lines = [
                f"- [[{event_notes[event['id']][:-3]}|{event.get('title')}]]"
                for event in rows[-100:]
            ]
            files[rel] = _index_page(name, []) + "\n## Events\n\n" + "\n".join(event_lines) + "\n"
        files[f"{folder}/Index.md"] = _index_page(label, sorted(index_rows))

    lesson_rows = [
        (event_notes[event["id"]][:-3], str(event.get("title") or "lesson"))
        for event in lessons[-200:]
    ]
    files["Lessons/Index.md"] = _index_page("Lessons", lesson_rows)

    chapter_rows = [
        (event_notes[event["id"]][:-3], str(event.get("title") or "chapter"))
        for event in chapters[-200:]
    ]
    files["Chapters/Index.md"] = _index_page("Chapters", chapter_rows)
    files["Attachments/.keep"] = ""

    result = _write_generated(root, files, force=force)
    exported = {
        "ok": True,
        "vault": str(root),
        "events": len(events),
        "daily_notes": len(by_day),
        "people": len(people),
        "projects": len(projects),
        "capabilities": len(capabilities),
        **result,
    }

    def _mutate(data):
        current = _normalize_state(data)
        current["last_export"] = {
            "at": _iso(),
            "vault": str(root),
            "events": len(events),
            "conflicts": len(result["conflicts"]),
        }
        current["updated_at"] = _iso()
        return current["last_export"]

    locked_json_update(_state_path(), _default_state(), _mutate, lock_timeout=10)
    try:
        audit("life_export", {
            "vault": str(root),
            "events": len(events),
            "created": len(result["created"]),
            "updated": len(result["updated"]),
            "conflicts": len(result["conflicts"]),
        })
    except Exception:
        pass
    return exported


def remember_work_log(row: dict, *, source_ref: str | None = None) -> dict:
    """把工作日志镜像成生命事件；同 source.ref 幂等。"""
    row = row if isinstance(row, dict) else {}
    action = str(row.get("action") or "work").lower()
    event_type = {
        "start": "task",
        "done": "milestone",
        "lesson": "lesson",
    }.get(action, "task")
    ref = source_ref or f"root_fix.work_log:{_digest(row)}"
    return record_event({
        "type": event_type,
        "title": _safe_text(row.get("title") or "工作记录", _MAX_TITLE),
        "summary": _safe_text(row.get("detail") or "", _MAX_TEXT),
        "at": row.get("at"),
        "importance": 0.72 if event_type == "milestone" else 0.55,
        "tags": ["work", action],
        "source": {
            "kind": "root_fix.work_log",
            "ref": ref,
            "digest": _digest(row),
        },
    })


def remember_lesson(situation: str, lesson: str, guard: str = "",
                    severity: str = "medium", source: str = "manual") -> dict:
    """把阅历镜像成生命事件，保留简短经验与防复发边界。"""
    summary = _safe_text(lesson, _MAX_TEXT)
    if guard:
        summary = _safe_text(f"{summary}；防护：{guard}", _MAX_TEXT)
    ref = "mind.lesson:" + _digest({
        "situation": situation,
        "lesson": lesson,
        "guard": guard,
        "source": source,
    })
    return record_event({
        "type": "lesson",
        "title": _safe_text(situation or "阅历沉淀", _MAX_TITLE),
        "summary": summary,
        "importance": 0.9 if severity in ("high", "critical") else 0.72,
        "tags": ["lesson", str(severity or "medium")],
        "source": {"kind": "mind.lesson", "ref": ref, "digest": ref.split(":", 1)[-1]},
    })


def remember_mind_event(event: str, pulse: dict, payload: dict | None = None) -> dict:
    """只把重要心智事件写成短生命轨迹，不保存完整消息或提示词。"""
    payload = payload if isinstance(payload, dict) else {}
    if payload.get("_probe"):
        return {"ok": True, "skipped": True, "reason": "probe"}
    event = str(event or "event").lower()
    importance = _clamp(
        payload.get("importance"),
        low=0.0,
        high=1.0,
    ) if payload.get("importance") is not None else 0.5
    owner = pulse.get("owner_model") or {}
    owner_state = str(owner.get("state") or "unknown")
    if event not in _CAPTURE_MIND_EVENTS:
        if event == "user_message" and (
            importance >= 0.8 or owner_state in {"fatigued", "frustrated", "urgent"}
        ):
            pass
        elif importance < 0.82:
            return {"ok": True, "skipped": True, "reason": "not_significant"}
    task = _safe_text(
        payload.get("task") or payload.get("goal") or payload.get("situation") or "",
        180,
    )
    decision = pulse.get("communication") or {}
    appraisal = pulse.get("appraisal") or {}
    summary_parts = []
    if task:
        summary_parts.append(task)
    if owner.get("current_need"):
        summary_parts.append(f"主人需要：{owner['current_need']}")
    if decision.get("action"):
        summary_parts.append(f"回应：{decision['action']}")
    if event in ("mistake", "task_failed", "corrected"):
        summary_parts.append(f"情绪：{pulse.get('mood') or '未知'}")
    summary = "；".join(summary_parts) or (
        f"{_EVENT_TITLES.get(event, event)}；情绪：{pulse.get('mood') or '未知'}"
    )
    event_type = {
        "mistake": "mistake",
        "corrected": "correction",
        "task_succeeded": "milestone",
        "task_failed": "lesson",
        "praise": "relationship",
        "criticism": "lesson",
        "affection": "relationship",
        "permission_denied": "boundary",
        "startup_ready": "milestone",
    }.get(event, "task")
    tags = [event, f"mood:{pulse.get('mood') or 'unknown'}",
            f"owner:{owner_state}"]
    ref = "mind.event:" + _digest({
        "event": event,
        "task": task,
        "owner_state": owner_state,
        "mood": pulse.get("mood"),
        "day": _now().strftime("%Y-%m-%d"),
    })
    return record_event({
        "type": event_type,
        "title": _EVENT_TITLES.get(event, f"心智事件：{event}"),
        "summary": summary,
        "importance": max(importance, 0.62 if event in _CAPTURE_MIND_EVENTS else 0.5),
        "confidence": owner.get("confidence") or 0.7,
        "valence": float(pulse.get("valence") or 0.5) * 2.0 - 1.0,
        "tags": tags,
        "source": {"kind": "mind_engine", "ref": ref, "digest": ref.split(":", 1)[-1]},
    })


def ingest_sources() -> dict:
    """把现有工作日志、反思、视觉记忆和心智历史汇入生命时间线。"""
    store = _store()
    recorded = []
    duplicates = []
    errors = []

    work_log = store / "work_log.jsonl"
    if work_log.exists():
        try:
            for line in work_log.read_text(encoding="utf-8", errors="replace").splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                result = remember_work_log(row)
                (duplicates if result.get("duplicate") else recorded).append(result)
        except Exception as exc:
            errors.append({"source": "work_log", "error": str(exc)[:160]})

    polish = load_json(store / "polish_insights.json", {}) or {}
    for row in polish.get("insights") or []:
        try:
            result = record_event({
                "type": "lesson",
                "title": _safe_text(row.get("title") or "推演反思", _MAX_TITLE),
                "summary": _safe_text(row.get("detail") or "", _MAX_TEXT),
                "importance": 0.76,
                "tags": ["reflection", "think_loop"],
                "source": {
                    "kind": "think_loop.polish_insights",
                    "ref": f"polish:{_digest(row)}",
                },
            })
            (duplicates if result.get("duplicate") else recorded).append(result)
        except Exception as exc:
            errors.append({"source": "polish_insights", "error": str(exc)[:160]})

    visual = load_json(store / "visual_memory" / "timeline.json", []) or []
    for row in visual:
        try:
            keywords = _safe_items(row.get("keywords"), limit=12, item_limit=60)
            summary = _safe_text(
                row.get("description")
                or ("视觉场景：" + "、".join(keywords) if keywords else "观察到一帧画面"),
                _MAX_TEXT,
            )
            result = record_event({
                "type": "perception",
                "title": "视觉记忆",
                "summary": summary,
                "at": row.get("timestamp"),
                "importance": 0.38,
                "confidence": 0.72,
                "tags": ["vision", str(row.get("channel") or "screen")],
                "source": {
                    "kind": "visual_memory",
                    "ref": f"visual:{row.get('frame_id') or _digest(row)}",
                },
            })
            (duplicates if result.get("duplicate") else recorded).append(result)
        except Exception as exc:
            errors.append({"source": "visual_memory", "error": str(exc)[:160]})

    mind = load_json(store / "mind_state.json", {}) or {}
    for index, row in enumerate(mind.get("history") or []):
        try:
            event_name = str(row.get("event") or "mind")
            result = record_event({
                "type": "reflection",
                "title": f"心智轨迹：{event_name}",
                "summary": (
                    f"情绪 {row.get('mood') or '未知'}；"
                    f"决策 {row.get('decision') or '无'}；"
                    f"主人状态 {row.get('owner_state') or 'unknown'}"
                ),
                "at": datetime.fromtimestamp(
                    float(row.get("at") or 0)).astimezone().isoformat(timespec="seconds")
                if row.get("at") else None,
                "importance": 0.48,
                "tags": ["mind", event_name],
                "source": {
                    "kind": "mind_engine.history",
                    "ref": f"mind-history:{index}:{_digest(row)}",
                },
            })
            (duplicates if result.get("duplicate") else recorded).append(result)
        except Exception as exc:
            errors.append({"source": "mind_history", "error": str(exc)[:160]})

    return {
        "ok": not errors,
        "recorded": len(recorded),
        "duplicates": len(duplicates),
        "errors": errors,
    }


def status() -> dict:
    """生命档案只读状态。"""
    state = _normalize_state(load_json(_state_path(), _default_state()))
    events = _load_events()
    return {
        "ok": True,
        "state": "alive",
        "events": len(events),
        "first_at": events[0].get("at") if events else None,
        "last_at": events[-1].get("at") if events else None,
        "counts": dict(Counter(
            str(event.get("type") or "event") for event in events)),
        "chapters": len(state.get("chapters") or []),
        "commitments": len(state.get("commitments") or []),
        "habits": len(state.get("habits") or []),
        "vault": str(_default_vault()),
        "last_export": state.get("last_export"),
        "operations": [
            "status", "record", "timeline", "today", "daily", "recall",
            "graph", "reflect", "chapter", "commitment", "habit",
            "export", "ingest",
        ],
    }


def run(op: str = "status", **params):
    """统一入口：生命事件、时光轴、章节、承诺、习惯、反思与 Vault 导出。"""
    op = str(op or "status").strip().lower()
    params.pop("_probe", None)
    if op == "status":
        return status()
    if op in ("record", "event", "remember"):
        value = params.get("event") if isinstance(params.get("event"), dict) else params
        return record_event(value)
    if op == "timeline":
        return timeline(
            start=params.get("start") or params.get("date_start"),
            end=params.get("end") or params.get("date_end"),
            event_type=params.get("type") or params.get("event_type"),
            tag=params.get("tag"),
            chapter=params.get("chapter"),
            limit=int(params.get("limit", 100) or 100),
            ascending=bool(params.get("ascending", True)),
        )
    if op in ("today", "day"):
        return build_daily(params.get("date"))
    if op == "daily":
        day = _safe_text(params.get("date"), 10) if params.get("date") else _now().strftime("%Y-%m-%d")
        return export_obsidian(params.get("vault"), force=bool(params.get("force"))) | {"date": day}
    if op == "recall":
        return recall(params.get("query", ""), int(params.get("limit", 10) or 10))
    if op == "graph":
        return graph(int(params.get("limit", 1000) or 1000))
    if op == "reflect":
        return reflect(
            params.get("period", "week"),
            save=bool(params.get("save", False)),
            note=params.get("note", ""),
        )
    if op == "chapter":
        return chapter(params.get("action") or "list", **{
            k: v for k, v in params.items() if k != "action"
        })
    if op == "commitment":
        return commitment(params.get("action") or "list", **{
            k: v for k, v in params.items() if k != "action"
        })
    if op == "habit":
        return habit(params.get("action") or "list", **{
            k: v for k, v in params.items() if k != "action"
        })
    if op in ("export", "export_obsidian", "vault"):
        return export_obsidian(
            params.get("vault") or params.get("path"),
            force=bool(params.get("force", False)),
        )
    if op in ("ingest", "import_sources", "sync_sources"):
        return ingest_sources()
    raise ValueError(
        "未知 life op，可用: status/record/timeline/today/daily/recall/"
        "graph/reflect/chapter/commitment/habit/export/ingest"
    )
