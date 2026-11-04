# -*- coding: utf-8 -*-
# gbt-capability: focus_stack  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""焦点栈 + 记忆审计（我们自己的 P1）。

对照上游参考项目的「焦点栈 / 记忆审计」（上游参考项目: focus threads + memory audit）：
只取**判据**，不搬它的 SQLite/表结构。

焦点栈：主循环「此刻最重要的事」的有界栈：
  · 上限 12；同 id 再压入=提分（不重复堆）；
  · score 0..100；按 score/时间排序；可 pop/clear；每一步落事件账；
记忆审计：对**调用方给的记录**做只读体检（本件不读盘）：
  · 缺 id/文本/时间 → 记问题；重复 id；空/过短/超长；
  · 明显凭据（sk-… / api_key= / password= / token=）→ 记 secret_like（不展示原文）；
  · 输出计数/问题列表/按类汇总，不修改任何记录。
"""
from __future__ import annotations

import hashlib
import re
import time

MAX_ITEMS = 12
MAX_TITLE = 120
MAX_TARGET = 300
MAX_TEXT = 2000
MAX_RECORDS = 500
_SECRET_RX = re.compile(
    r"(sk-[A-Za-z0-9_-]{10,}|api[_-]?key\s*[:=]\s*\S+|password\s*[:=]\s*\S+|"
    r"token\s*[:=]\s*[A-Za-z0-9._-]{8,})", re.I)
_ID_RX = re.compile(r"^[A-Za-z0-9_.:-]{1,80}$")


class FocusError(ValueError):
    pass


def _text(value, name, max_len, required=False):
    s = str(value or "")
    if required and not s.strip():
        raise FocusError("%s 不能为空" % name)
    if len(s) > max_len:
        raise FocusError("%s 超长（>%d）" % (name, max_len))
    return s.strip()


def _score(value) -> int:
    try:
        v = int(value)
    except (TypeError, ValueError):
        raise FocusError("score 必须是整数 0..100")
    if v < 0 or v > 100:
        raise FocusError("score 范围 0..100")
    return v


class FocusStack:
    def __init__(self, clock=time.time, max_items: int = MAX_ITEMS):
        self.clock = clock
        self.max_items = int(max_items)
        self.items = {}
        self.events = []

    def _log(self, typ, **kw):
        self.events.append({"type": typ, "at": self.clock(), **kw})
        self.events = self.events[-200:]

    def push(self, item) -> dict:
        if not isinstance(item, dict):
            raise FocusError("item 必须是对象")
        iid = _text(item.get("id"), "id", 80)
        if not iid:
            iid = "fx-%d" % int(self.clock() * 1000)
        if not _ID_RX.match(iid):
            raise FocusError("id 只许字母数字_.:-（≤80）")
        title = _text(item.get("title"), "title", MAX_TITLE, required=True)
        target = _text(item.get("target"), "target", MAX_TARGET)
        kind = _text(item.get("kind"), "kind", 32) or "task"
        score = _score(item.get("score", 50))
        if iid in self.items:
            old = self.items[iid]
            old["score"] = min(100, max(old["score"], score) + 1)
            old["title"] = title
            old["target"] = target
            old["kind"] = kind
            old["at"] = self.clock()
            self._log("bump", id=iid, score=old["score"])
            return {"ok": True, "item": dict(old), "bumped": True}
        if len(self.items) >= self.max_items:
            low = min(self.items.values(), key=lambda x: (x["score"], x["at"]))
            self.items.pop(low["id"], None)
            self._log("evict", id=low["id"])
        row = {"id": iid, "title": title, "target": target, "kind": kind,
               "score": score, "at": self.clock()}
        self.items[iid] = row
        self._log("push", id=iid, score=score)
        return {"ok": True, "item": dict(row), "bumped": False}

    def pop(self, item_id=None) -> dict:
        if item_id:
            row = self.items.pop(str(item_id), None)
            if not row:
                return {"ok": False, "error": "no_such_item"}
            self._log("pop", id=row["id"])
            return {"ok": True, "item": row}
        if not self.items:
            return {"ok": False, "error": "empty"}
        row = self.top()
        self.items.pop(row["id"], None)
        self._log("pop", id=row["id"])
        return {"ok": True, "item": row}

    def top(self):
        if not self.items:
            return None
        return max(self.items.values(), key=lambda x: (x["score"], x["at"]))

    def clear(self) -> dict:
        n = len(self.items)
        self.items.clear()
        self._log("clear", n=n)
        return {"ok": True, "cleared": n}

    def snapshot(self) -> dict:
        rows = sorted(self.items.values(), key=lambda x: (-x["score"], -x["at"]))
        return {"ok": True, "items": rows, "count": len(rows), "max": self.max_items,
                "top": self.top()}

    def events_tail(self, n: int = 50) -> list:
        return list(self.events[-int(n):])


_BOARD = FocusStack()


def audit_records(records) -> dict:
    """只读体检：不读盘/不改记录/不回显凭据原文。"""
    if not isinstance(records, list):
        return {"ok": False, "error": "user_error: records 必须是数组", "count": 0, "issues": []}
    records = records[:MAX_RECORDS]
    issues = []
    seen = set()
    totals = {"records": len(records), "issues": 0, "duplicate_ids": 0,
              "missing_text": 0, "missing_time": 0, "secret_like": 0,
              "too_long": 0, "too_short": 0}
    for i, r in enumerate(records):
        if not isinstance(r, dict):
            issues.append({"index": i, "issue": "not_object"})
            continue
        rid = str(r.get("id") or r.get("ref") or "").strip()
        text = str(r.get("text") or r.get("content") or r.get("summary")
                   or r.get("why") or "").strip()
        at = r.get("at") or r.get("ts") or r.get("time")
        if not rid:
            issues.append({"index": i, "issue": "missing_id"})
        elif rid in seen:
            totals["duplicate_ids"] += 1
            issues.append({"index": i, "id": rid, "issue": "duplicate_id"})
        else:
            seen.add(rid)
        if not text:
            totals["missing_text"] += 1
            issues.append({"index": i, "id": rid, "issue": "missing_text"})
        else:
            if len(text) < 4:
                totals["too_short"] += 1
                issues.append({"index": i, "id": rid, "issue": "too_short"})
            if len(text) > MAX_TEXT:
                totals["too_long"] += 1
                issues.append({"index": i, "id": rid, "issue": "too_long"})
            if _SECRET_RX.search(text):
                totals["secret_like"] += 1
                issues.append({"index": i, "id": rid, "issue": "secret_like"})
        if not at:
            totals["missing_time"] += 1
            issues.append({"index": i, "id": rid, "issue": "missing_time"})
    totals["issues"] = len(issues)
    return {"ok": True, "count": len(records), "issues": issues[:100],
            "totals": totals,
            "verdict": "clean" if not issues else "needs_review"}


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    now = [1000.0]
    st = FocusStack(clock=lambda: now[0])
    r = st.push({"id": "a", "title": "看一下构建", "score": 60})
    ck("push", r["ok"] and st.snapshot()["count"] == 1)
    r = st.push({"id": "a", "title": "看一下构建", "score": 70})
    ck("同 id 提分不重复", r.get("bumped") is True and st.snapshot()["count"] == 1)
    st.push({"id": "b", "title": "回主人", "score": 80})
    ck("top 分数最高", st.top()["id"] == "b")
    ck("snapshot 排序", [x["id"] for x in st.snapshot()["items"]] == ["b", "a"])
    ck("pop top", st.pop()["item"]["id"] == "b")
    ck("pop 指定", st.pop("a")["ok"])
    ck("空栈 pop 拒", st.pop()["ok"] is False)
    now[0] += 1
    st.push({"id": "c", "title": "c"})
    ck("clear", st.clear()["ok"] and st.snapshot()["count"] == 0)
    ck("空 id 自动生成", st.push({"title": "无 id"})["ok"])
    ck("title 必填", _raises(lambda: FocusStack().push({"id": "x", "title": ""})))
    ck("score 越界", _raises(lambda: FocusStack().push({"id": "x", "title": "x", "score": 101})))
    st2 = FocusStack(max_items=2, clock=lambda: 1.0)
    st2.push({"id": "1", "title": "1"}); st2.push({"id": "2", "title": "2"})
    st2.push({"id": "3", "title": "3"})
    ck("上限逐出", st2.snapshot()["count"] == 2)
    a = audit_records([
        {"id": "m1", "text": "主人喜欢短句", "at": "2026-11-02", "origin": "主人令"},
        {"id": "m1", "text": "x", "at": ""},
        {"id": "m2", "text": "api_key=sk-" + "A" * 20, "at": "2026-11-02"},
        {"id": "", "text": "", "at": ""},
    ])
    ck("审计有问题", a["ok"] and a["verdict"] == "needs_review" and a["totals"]["duplicate_ids"] == 1, a["totals"])
    ck("审计识别 secret_like", a["totals"]["secret_like"] == 1)
    ck("审计不回显凭据原文", "sk-" + "A" * 20 not in str(a["issues"]))
    clean = audit_records([{"id": "m3", "text": "正常记忆", "at": "2026-11-02"}])
    ck("干净记录 verdict", clean["verdict"] == "clean" and clean["totals"]["issues"] == 0)
    ck("审计空列表", audit_records([])["verdict"] == "clean")
    ck("审计非数组拒", audit_records("x")["ok"] is False)
    return {"ok": all(x["ok"] for x in checks), "checks": len(checks),
            "failed": [x for x in checks if not x["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except FocusError:
        return True


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op == "schema":
        return {"ok": True, "max_items": MAX_ITEMS, "max_records": MAX_RECORDS,
                "max_title": MAX_TITLE, "max_text": MAX_TEXT,
                "note": "focus stack+memory audit；只读审计不改记录"}
    if op == "push":
        try:
            return _BOARD.push(params.get("item"))
        except FocusError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "pop":
        return _BOARD.pop(params.get("id"))
    if op == "clear":
        return _BOARD.clear()
    if op == "snapshot":
        return _BOARD.snapshot()
    if op == "audit":
        return audit_records(params.get("records"))
    if op == "focus_events":
        return {"ok": True, "events": _BOARD.events_tail(params.get("n", 50))}
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/push/pop/clear/snapshot/audit/focus_events/verify）" % op)
