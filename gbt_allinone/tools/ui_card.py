# -*- coding: utf-8 -*-
# gbt-capability: ui_card  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""ui_card / ACUI 卡片协议（我们自己的）。

对照上游参考项目的 `SCENE-PROTOCOL.md` + `ACUI (Remix)/*`（天气/自检/唤醒/图片/视频/确认卡）：
只蒸**协议与判据**，不搬 React/他们的渲染。

铁律：
  ① 卡片是**数据**：纯文本渲染，不允许 HTML/脚本/事件属性；
  ② 白名单：kind / action.type 不在表里的直接拒；
  ③ 动作只**回发事件**给主循环，不在这里执行任何工具；
  ④ TTL：过期自动消失；账本只记 create/close/action，可审计；
  ⑤ 上限：最多 20 张、同时最多 4 个 action、body ≤2000 字。
"""
from __future__ import annotations

import hashlib
import re
import time

KINDS = ("info", "selfcheck", "wake", "image", "video", "confirm", "weather")
ACTION_TYPES = ("confirm", "dismiss", "open", "send", "link")
MAX_CARDS = 20
MAX_ACTIONS = 4
MAX_BODY = 2000
MAX_TITLE = 120
MAX_TTL = 86400
DEFAULT_TTL = 300
_ID_RX = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ACTION_ID_RX = re.compile(r"^[a-z0-9_-]{1,32}$")
_SCRIPT_RX = re.compile(r"<\s*/?\s*(script|style|iframe|object|embed)\b|javascript\s*:|on[a-z]+\s*=", re.I)


class UIError(ValueError):
    pass


def _text(value, name, max_len, required=False):
    s = str(value or "")
    if required and not s.strip():
        raise UIError("%s 不能为空" % name)
    if len(s) > max_len:
        raise UIError("%s 超长（>%d）" % (name, max_len))
    return s.strip()


def _safe_text(value, name, max_len, required=False):
    s = _text(value, name, max_len, required)
    if _SCRIPT_RX.search(s):
        raise UIError("%s 含 HTML/脚本/事件属性（只许纯文本）" % name)
    return s


def normalize_card(card) -> dict:
    """校验并归一化一张卡；白名单外/注入/越界直接 UIError。"""
    if not isinstance(card, dict):
        raise UIError("card 必须是对象")
    kind = str(card.get("kind") or "").strip().lower()
    if kind not in KINDS:
        raise UIError("未知 kind: %s（允许 %s）" % (kind, ",".join(KINDS)))
    title = _safe_text(card.get("title"), "title", MAX_TITLE, required=True)
    body = _safe_text(card.get("body"), "body", MAX_BODY)
    source = _text(card.get("source"), "source", 80)
    cid = str(card.get("id") or "").strip()
    if not cid:
        cid = "uc-%d-%04x" % (int(time.time() * 1000), int(hashlib.sha256(title.encode()).hexdigest()[:4], 16))
    if not _ID_RX.match(cid):
        raise UIError("id 只许字母数字_-（≤64）")
    try:
        ttl = int(card.get("ttl", DEFAULT_TTL))
    except (TypeError, ValueError):
        raise UIError("ttl 必须是整数秒")
    if ttl < 0 or ttl > MAX_TTL:
        raise UIError("ttl 范围 0..%d" % MAX_TTL)
    raw_actions = card.get("actions") or []
    if not isinstance(raw_actions, list):
        raise UIError("actions 必须是数组")
    if len(raw_actions) > MAX_ACTIONS:
        raise UIError("actions 最多 %d 个" % MAX_ACTIONS)
    actions = []
    seen = set()
    for a in raw_actions:
        if not isinstance(a, dict):
            raise UIError("action 必须是对象")
        aid = str(a.get("id") or "").strip().lower()
        if not _ACTION_ID_RX.match(aid):
            raise UIError("action.id 只许小写字母数字_-（≤32）")
        if aid in seen:
            raise UIError("action.id 重复: %s" % aid)
        seen.add(aid)
        typ = str(a.get("type") or "confirm").strip().lower()
        if typ not in ACTION_TYPES:
            raise UIError("未知 action.type: %s" % typ)
        label = _safe_text(a.get("label") or aid, "action.label", 40, required=True)
        actions.append({"id": aid, "type": typ, "label": label})
    return {"id": cid, "kind": kind, "title": title, "body": body,
            "actions": actions, "ttl": ttl, "source": source,
            "created_at": float(card.get("created_at") or time.time())}


def render_card(card, now: float | None = None) -> dict:
    now = float(now if now is not None else time.time())
    expires = float(card.get("created_at") or now) + float(card.get("ttl") or 0)
    return {"id": card["id"], "kind": card["kind"], "title": card["title"],
            "body": card["body"], "actions": card["actions"],
            "source": card.get("source") or "",
            "ttl": card.get("ttl") or 0,
            "remaining": max(0, int(expires - now)),
            "expired": now >= expires}


def action_event(card_id: str, action: dict, extra=None) -> dict:
    """动作只回发事件；`executed` 恒为 False（不在卡片层执行任何工具）。"""
    ev = {"type": "ui_card_action", "card_id": card_id,
          "action": {"id": action["id"], "type": action["type"], "label": action["label"]},
          "executed": False,
          "note": "只回发事件给主循环；工具执行仍走统一门"}
    if extra:
        ev["payload"] = extra
    return ev


class CardBoard:
    """内存卡片板（TTL/上限/审计事件）；不落盘由调用方决定。"""

    def __init__(self, clock=time.time, max_cards: int = MAX_CARDS):
        self.clock = clock
        self.max_cards = int(max_cards)
        self.cards = {}
        self.events = []

    def _purge(self):
        now = self.clock()
        for cid in list(self.cards):
            if now >= self.cards[cid]["_expires"]:
                card = self.cards.pop(cid)
                self.events.append({"type": "expired", "card_id": cid,
                                    "at": now, "kind": card["kind"]})
        return now

    def create(self, raw) -> dict:
        card = normalize_card(raw)
        # 创建时间统一用卡片板时钟（测试可注入；真实环境=time.time），否则 TTL 测试与时钟不一致
        card["created_at"] = float((raw or {}).get("created_at") or self.clock())
        self._purge()
        if len(self.cards) >= self.max_cards:
            oldest = min(self.cards.values(), key=lambda c: c["created_at"])
            self.cards.pop(oldest["id"], None)
            self.events.append({"type": "evicted", "card_id": oldest["id"], "at": self.clock()})
        card["_expires"] = card["created_at"] + card["ttl"]
        self.cards[card["id"]] = card
        self.events.append({"type": "create", "card_id": card["id"], "kind": card["kind"],
                            "at": self.clock()})
        return render_card(card, self.clock())

    def close(self, card_id: str, reason: str = "close") -> dict:
        card = self.cards.pop(str(card_id), None)
        if not card:
            return {"ok": False, "error": "no_such_card"}
        self.events.append({"type": reason, "card_id": card["id"], "at": self.clock()})
        return {"ok": True, "closed": card["id"]}

    def act(self, card_id: str, action_id: str, payload=None) -> dict:
        self._purge()
        card = self.cards.get(str(card_id))
        if not card:
            return {"ok": False, "error": "no_such_card"}
        action = next((a for a in card["actions"] if a["id"] == str(action_id)), None)
        if not action:
            return {"ok": False, "error": "no_such_action"}
        ev = action_event(card["id"], action, payload)
        self.events.append({"type": "action", "card_id": card["id"],
                            "action": action["id"], "at": self.clock(),
                            "executed": False})
        return {"ok": True, "event": ev, "card": render_card(card, self.clock())}

    def snapshot(self) -> dict:
        now = self._purge()
        rows = [render_card(c, now) for c in sorted(self.cards.values(),
                                                     key=lambda c: c["created_at"])]
        return {"ok": True, "cards": rows, "count": len(rows),
                "max": self.max_cards, "at": now}


_BOARD = CardBoard()


def run(op="schema", **params):
    op = str(op or "schema").lower()
    if op == "schema":
        return {"ok": True, "kinds": list(KINDS), "action_types": list(ACTION_TYPES),
                "limits": {"cards": MAX_CARDS, "actions": MAX_ACTIONS,
                           "title": MAX_TITLE, "body": MAX_BODY, "ttl": MAX_TTL}}
    if op == "validate":
        try:
            return {"ok": True, "card": normalize_card(params.get("card"))}
        except UIError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "create":
        try:
            card = _BOARD.create(params.get("card"))
            return {"ok": True, "card": card, "cards": _BOARD.snapshot()}
        except UIError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "close":
        return _BOARD.close(str(params.get("id") or ""),
                            str(params.get("reason") or "closed"))
    if op == "action":
        r = _BOARD.act(str(params.get("id") or ""), str(params.get("action") or ""),
                       params.get("payload"))
        return r
    if op == "snapshot":
        return _BOARD.snapshot()
    if op == "events":
        return {"ok": True, "events": list(_BOARD.events[-100:])}
    if op == "clear":
        _BOARD.cards.clear()
        return {"ok": True, "cleared": True}
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/validate/create/close/action/snapshot/events/clear/verify）" % op)


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    good = {"kind": "info", "title": "自检", "body": "一切正常",
            "actions": [{"id": "ok", "type": "confirm", "label": "知道了"}]}
    c = normalize_card(good)
    ck("合法卡归一", c["kind"] == "info" and c["id"].startswith("uc-"), c["id"])
    ck("白名单 kind 外拒", _raises(lambda: normalize_card({"kind": "evil", "title": "x"})))
    ck("空标题拒", _raises(lambda: normalize_card({"kind": "info", "title": ""})))
    ck("body 超长拒", _raises(lambda: normalize_card({"kind": "info", "title": "x", "body": "a" * 2001})))
    ck("脚本注入拒", _raises(lambda: normalize_card({"kind": "info", "title": "<script>x</script>"})))
    ck("事件属性拒", _raises(lambda: normalize_card({"kind": "info", "title": "x", "body": "<img onerror=1>"})))
    ck("javascript: 拒", _raises(lambda: normalize_card({"kind": "info", "title": "x", "body": "javascript:alert(1)"})))
    ck("未知 action.type 拒", _raises(lambda: normalize_card({
        "kind": "info", "title": "x", "actions": [{"id": "a", "type": "rm -rf", "label": "x"}]})))
    ck("action 上限", _raises(lambda: normalize_card({
        "kind": "info", "title": "x", "actions": [{"id": "a%d" % i, "type": "confirm", "label": "x"} for i in range(5)]})))
    ck("ttl 越界拒", _raises(lambda: normalize_card({"kind": "info", "title": "x", "ttl": 999999})))
    ck("ttl 默认 300", normalize_card({"kind": "info", "title": "x"})["ttl"] == 300)
    ck("渲染 remaining", render_card(c, now=c["created_at"] + 10)["remaining"] == 290)
    board = CardBoard(clock=lambda: 1000.0)
    card = board.create(good)
    ck("board create", card["kind"] == "info")
    ck("snapshot 有卡", board.snapshot()["count"] == 1)
    ck("未知 action 拒", board.act(card["id"], "nope")["ok"] is False)
    ev = board.act(card["id"], "ok")
    ck("动作只回事件不执行", ev["ok"] and ev["event"]["executed"] is False
       and ev["event"]["type"] == "ui_card_action")
    ck("close 生效", board.close(card["id"])["ok"] and board.snapshot()["count"] == 0)
    now = [2000.0]
    b2 = CardBoard(clock=lambda: now[0])
    b2.create({"kind": "info", "title": "短期", "ttl": 5})
    now[0] += 10
    ck("TTL 过期清理", b2.snapshot()["count"] == 0)
    b3 = CardBoard(max_cards=1)
    b3.create({"kind": "info", "title": "一"})
    b3.create({"kind": "info", "title": "二"})
    ck("上限逐出最旧", len(b3.snapshot()["cards"]) == 1)
    ck("事件账有记录", any(e["type"] == "create" for e in b3.events))
    ck("schema 有白名单", set(run("schema")["kinds"]) >= {"info", "confirm", "selfcheck"})
    ck("ops schema 可达", run("schema")["ok"] is True
       and set(run("schema")["action_types"]) == set(ACTION_TYPES))
    return {"ok": all(x["ok"] for x in checks), "checks": len(checks),
            "failed": [x for x in checks if not x["ok"]],
            "sha": hashlib.sha256(str(checks).encode("utf-8")).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except UIError:
        return True
