# -*- coding: utf-8 -*-
# gbt-capability: reminder  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""提醒能力位（reminder）—— 我们自己的 P1。

对照上游参考项目的提醒/日程：只蒸**创建/列出/取消**的最小闭环，不搬它的调度器/通知渠道。
写面纪律（与 anatomy_cap/actioncam 同口径）：
  · create/cancel/complete 写 `state/reminders.json` ⇒ 先过 `filesystem_write` 门；
  · 可信会话（主人本机）免票，其余一律要一次性授权（auth_gate）；
  · 读面（list/due）免门；不做网络通知，不偷偷起后台线程。
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_STATE = _ROOT / "state"
DEFAULT_PATH = _STATE / "reminders.json"
MAX_ITEMS = 200
MAX_TITLE = 120
MAX_NOTE = 500
REPEATS = ("none", "daily", "weekly")
STATUSES = ("pending", "done", "cancelled")
_ID_RX = re.compile(r"^rm-[0-9]+-[0-9a-f]{4}$")
_DT_FORMATS = ("%Y-%m-%dT%H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M",
               "%Y-%m-%d %H:%M:%S", "%Y-%m-%d")


class ReminderError(ValueError):
    pass


def _default_gate(detail: str):
    from ..security import policy as _policy
    if _policy.is_trusted():
        return None
    try:
        from .. import auth_gate
        got = auth_gate.check_and_consume("filesystem_write", detail=str(detail)[:60])
        if got.get("ok"):
            return None
        return {"ok": False, "denied": True, "gate": "filesystem_write",
                "error": got.get("error"), "how_to_grant": got.get("how_to_grant"),
                "note": "提醒写面必须过 filesystem_write 门"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "denied": True, "gate": "filesystem_write",
                "error": "gate 不可用，fail-closed: %s" % type(e).__name__}


def parse_due(value) -> float:
    if value is None or value == "":
        raise ReminderError("due_at 必填")
    if isinstance(value, (int, float)):
        ts = float(value)
    else:
        s = str(value).strip()
        if s.replace(".", "", 1).isdigit():
            ts = float(s)
        else:
            ts = None
            for fmt in _DT_FORMATS:
                try:
                    ts = time.mktime(time.strptime(s, fmt))
                    break
                except ValueError:
                    continue
            if ts is None:
                raise ReminderError("due_at 格式只许 YYYY-MM-DDTHH:MM[:SS] 或 epoch 秒")
    if ts < 0 or ts > 4102444800:  # 2100
        raise ReminderError("due_at 超出范围")
    return float(ts)


class ReminderStore:
    def __init__(self, path=DEFAULT_PATH, gate_fn=None, clock=time.time):
        self.path = Path(path)
        self.gate_fn = gate_fn if gate_fn is not None else _default_gate
        self.clock = clock

    def _load(self) -> list:
        try:
            if not self.path.is_file():
                return []
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:  # noqa: BLE001
            return []

    def _save(self, rows: list) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    def _gated(self, detail: str):
        g = self.gate_fn(detail)
        return g if isinstance(g, dict) and not g.get("ok", True) else None

    def create(self, raw) -> dict:
        if not isinstance(raw, dict):
            raise ReminderError("reminder 必须是对象")
        title = str(raw.get("title") or "").strip()
        if not title:
            raise ReminderError("title 必填")
        if len(title) > MAX_TITLE:
            raise ReminderError("title 超长（>%d）" % MAX_TITLE)
        note = str(raw.get("note") or "").strip()
        if len(note) > MAX_NOTE:
            raise ReminderError("note 超长（>%d）" % MAX_NOTE)
        due_ts = parse_due(raw.get("due_at") or raw.get("due_ts"))
        repeat = str(raw.get("repeat") or "none").lower()
        if repeat not in REPEATS:
            raise ReminderError("repeat 只许 %s" % ",".join(REPEATS))
        rows = self._load()
        if len(rows) >= MAX_ITEMS:
            return {"ok": False, "error": "too_many_reminders", "max": MAX_ITEMS}
        g = self._gated("reminder.create:" + title[:40])
        if g:
            return g
        now = self.clock()
        rid = "rm-%d-%04x" % (int(now * 1000), int.from_bytes(
            hashlib.sha256((title + str(due_ts) + str(now)).encode()).digest()[:2], "big") & 0xFFFF)
        row = {"id": rid, "title": title, "note": note, "due_at": time.strftime(
            "%Y-%m-%dT%H:%M:%S", time.localtime(due_ts)), "due_ts": due_ts,
            "repeat": repeat, "status": "pending", "created_at": time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.localtime(now))}
        rows.append(row)
        self._save(rows)
        return {"ok": True, "reminder": row, "count": len(rows)}

    def cancel(self, rid) -> dict:
        rid = str(rid or "")
        if not _ID_RX.match(rid):
            return {"ok": False, "error": "user_error: 提醒 id 非法"}
        rows = self._load()
        hit = next((r for r in rows if r.get("id") == rid), None)
        if not hit:
            return {"ok": False, "error": "no_such_reminder"}
        if hit.get("status") != "pending":
            return {"ok": False, "error": "already_" + str(hit.get("status"))}
        g = self._gated("reminder.cancel:" + rid)
        if g:
            return g
        hit["status"] = "cancelled"
        self._save(rows)
        return {"ok": True, "reminder": hit, "count": len(rows)}

    def complete(self, rid) -> dict:
        rid = str(rid or "")
        rows = self._load()
        hit = next((r for r in rows if r.get("id") == rid), None)
        if not hit:
            return {"ok": False, "error": "no_such_reminder"}
        if hit.get("status") != "pending":
            return {"ok": False, "error": "already_" + str(hit.get("status"))}
        g = self._gated("reminder.complete:" + rid)
        if g:
            return g
        hit["status"] = "done"
        hit["done_at"] = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self.clock()))
        self._save(rows)
        return {"ok": True, "reminder": hit, "count": len(rows)}

    def list(self, include_closed=True) -> dict:
        rows = self._load()
        if not include_closed:
            rows = [r for r in rows if r.get("status") == "pending"]
        rows.sort(key=lambda r: (r.get("status") != "pending", r.get("due_ts") or 0))
        return {"ok": True, "reminders": rows, "count": len(rows),
                "pending": sum(1 for r in rows if r.get("status") == "pending")}

    def due(self, now=None) -> dict:
        now = float(now if now is not None else self.clock())
        rows = [r for r in self._load()
                if r.get("status") == "pending" and float(r.get("due_ts") or 0) <= now]
        rows.sort(key=lambda r: r.get("due_ts") or 0)
        return {"ok": True, "due": rows, "count": len(rows), "at": now}


_BOARD = ReminderStore()


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    import tempfile
    d = tempfile.mkdtemp(prefix="gbt-rem-")
    p = Path(d) / "reminders.json"
    st = ReminderStore(path=p, gate_fn=lambda _d: None, clock=lambda: 1000.0)
    r = st.create({"title": "回主人", "due_at": "2026-11-03T10:00", "note": "x"})
    ck("创建", r["ok"] and r["reminder"]["status"] == "pending", r)
    ck("id 形态", bool(_ID_RX.match(r["reminder"]["id"])), r.get("reminder", {}).get("id"))
    ck("落盘", p.is_file() and len(st.list()["reminders"]) == 1)
    ck("due 到点", st.due(time.mktime(time.strptime("2026-11-03 10:00", "%Y-%m-%d %H:%M")))["count"] == 1)
    ck("due 未到", st.due(time.mktime(time.strptime("2026-11-03 09:00", "%Y-%m-%d %H:%M")))["count"] == 0)
    ck("取消", st.cancel(r["reminder"]["id"])["reminder"]["status"] == "cancelled")
    ck("已取消再取消拒", st.cancel(r["reminder"]["id"])["ok"] is False)
    r2 = st.create({"title": "第二个", "due_at": "2026-11-03 11:00"})
    ck("完成", st.complete(r2["reminder"]["id"])["reminder"]["status"] == "done")
    ck("title 必填", _raises(lambda: st.create({"due_at": "2026-11-03T10:00"})))
    ck("due 必填", _raises(lambda: st.create({"title": "x"})))
    ck("due 非法", _raises(lambda: st.create({"title": "x", "due_at": "明天"})))
    ck("repeat 白名单", _raises(lambda: st.create({"title": "x", "due_at": 1, "repeat": "hourly"})))
    ck("id 非法取消", st.cancel("bad")["ok"] is False)
    denied = ReminderStore(path=Path(d) / "deny.json",
                           gate_fn=lambda _d: {"ok": False, "denied": True, "gate": "filesystem_write"})
    ck("写面门拒", denied.create({"title": "x", "due_at": "2026-11-03T10:00"})["ok"] is False)
    ck("门拒不落盘", not (Path(d) / "deny.json").exists())
    ck("list 只读", st.list()["ok"] and "pending" in st.list())
    ck("schema 可达", "repeats" in run("schema") and "max_items" in run("schema"))
    ck("未知 op 拒", _raises(lambda: run("teleport")))
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except (ReminderError, ValueError):
        return True


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op == "schema":
        return {"ok": True, "max_items": MAX_ITEMS, "max_title": MAX_TITLE,
                "max_note": MAX_NOTE, "repeats": list(REPEATS), "statuses": list(STATUSES),
                "gate": "filesystem_write（写面；可信会话免票）",
                "note": "创建/列出/取消；不做网络通知/后台线程"}
    if op == "create":
        try:
            return _BOARD.create(params.get("reminder"))
        except ReminderError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "list":
        return _BOARD.list(params.get("include_closed", True))
    if op == "cancel":
        return _BOARD.cancel(params.get("id"))
    if op == "complete":
        return _BOARD.complete(params.get("id"))
    if op == "due":
        return _BOARD.due(params.get("now"))
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/create/list/cancel/complete/due/verify）" % op)
