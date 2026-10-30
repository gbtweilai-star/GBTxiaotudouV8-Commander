# -*- coding: utf-8 -*-
"""主动性引擎（2026-10-30 · 照 dsh-pet 的调度模型实现，不搬它的 Node 代码）

为什么要它：主人要的是**不等指令的智能体**。dsh-pet 那套"主动性"其实由四件事组成，
这里逐条落地：

  ① 待办 + 提醒密度升级（它 FEATURES 第 5 条的口径，逐字照做）：
     距到期 7 天内开始提醒：24h → 12h → 4h → 1h → 20m → 5m
     逾期 <1 天：每 30 分钟；<1 周：每 6 小时；再久就不打扰
  ② 一次只让一只宠物说，气泡停 15 秒
  ③ 当前没有端在线时**先不说**，等有端连上再补（不丢，不乱）
  ④ 睡觉时彻底安静（不提醒、不随机动作），只按周期说梦话

外加一条我们自己的：**自己找活干**（initiative）—— 巡检/整理/学习三类，
按"上次做过多久"排队，没有待办时也不会干等着。

数据：state/proactive.json（待办 + 状态）、state/proactive_feed.jsonl（要说的话，页面来取）
"""
from __future__ import annotations

import json
import random
import time
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "proactive.json"
FEED = ROOT / "state" / "proactive_feed.jsonl"
BUBBLE_S = 15          # 气泡停留（照 dsh-pet）
NEAR_WINDOW_S = 7 * 86400

# 距到期的提醒档（秒）—— dsh-pet 的 6 档逐字照抄
NEAR_STEPS = [24 * 3600, 12 * 3600, 4 * 3600, 3600, 20 * 60, 5 * 60]
OVERDUE_DAY = 30 * 60      # 逾期 1 天内：每 30 分钟
OVERDUE_WEEK = 6 * 3600    # 逾期 1 周内：每 6 小时
OVERDUE_STOP = 7 * 86400   # 再久不再打扰

# 没有待办时自己找的活（intiative），按最小间隔排队
INITIATIVES = [
    ("checkup", 3 * 3600, "我自己巡一圈：服务面 + 触手 + 树规"),
    ("tidy", 6 * 3600, "整理一下今天的工作台（清临时件、对账本）"),
    ("learn", 12 * 3600, "读一读今天新出现的东西，记一条笔记"),
]


def _load() -> dict:
    if STATE.is_file():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:                                          # noqa: BLE001
            pass
    return {"todos": [], "sleep": False, "clients": {}, "last_said": {},
            "last_initiative": {}, "seq": 0}


def _save(st: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def now() -> float:
    return time.time()


# ── 待办 ────────────────────────────────────────────────────────────────
def todo_add(text: str, due_ts: float | None = None) -> dict:
    st = _load()
    st["seq"] += 1
    item = {"id": "t%d" % st["seq"], "text": str(text)[:200], "done": False,
            "due": (float(due_ts) if due_ts else None),
            "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    st["todos"].append(item)
    _save(st)
    return {"ok": True, "todo": item}


def todo_list() -> dict:
    st = _load()
    items = [t for t in st["todos"] if not t.get("done")]
    items.sort(key=lambda t: (t.get("due") is None, t.get("due") or 0))
    return {"ok": True, "todos": items, "done": len([t for t in st["todos"] if t.get("done")])}


def todo_done(tid: str) -> dict:
    st = _load()
    for t in st["todos"]:
        if t["id"] == tid:
            t["done"] = True
            _save(st)
            return {"ok": True, "id": tid}
    return {"ok": False, "error": "没有这条待办：%s" % tid}


# ── 端在线 / 睡觉 ───────────────────────────────────────────────────────
def heartbeat(surface: str = "web") -> dict:
    st = _load()
    st["clients"][surface] = now()
    _save(st)
    return {"ok": True, "sleep": st.get("sleep", False)}


def set_sleep(on: bool) -> dict:
    st = _load()
    st["sleep"] = bool(on)
    _save(st)
    return {"ok": True, "sleep": st["sleep"]}


def _online(st: dict, ttl: float = 60) -> bool:
    t = now()
    return any(t - v < ttl for v in (st.get("clients") or {}).values())


# ── 提醒密度：算出"这一条现在该不该说" ──────────────────────────────────
def due_gap(due: float, t: float) -> float | None:
    """返回"该隔多久说一次"（秒）；None = 现在不该说。"""
    left = due - t
    if left > NEAR_WINDOW_S:
        return None                                   # 还远，不打扰
    if left > 0:
        # 取一个比 left 更紧的档：left=23h ⇒ 该按 24h 档（即已进档）
        for step in NEAR_STEPS:
            if left <= step:
                return step
        return NEAR_STEPS[0]
    over = -left
    if over <= 86400:
        return OVERDUE_DAY
    if over <= OVERDUE_STOP:
        return OVERDUE_WEEK
    return None                                       # 再久不再打扰


def _say(st: dict, kind: str, text: str, key: str) -> None:
    """把一句话放进 feed（页面来取）。一次只让一只说 —— 由页面侧保证唯一展示。"""
    FEED.parent.mkdir(parents=True, exist_ok=True)
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "kind": kind,
           "text": str(text)[:300], "bubble_s": BUBBLE_S, "key": key}
    with FEED.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    st["last_said"][key] = now()


def tick(force: bool = False) -> dict:
    """一次心跳：算所有该说的话，写进 feed。"""
    st = _load()
    t = now()
    out = {"ok": True, "said": [], "sleep": st.get("sleep", False),
           "online": _online(st), "skipped": []}

    if st.get("sleep") and not force:
        # 睡觉：彻底安静；只按周期说梦话（20 分钟一句）
        last = st.get("last_said", {}).get("dream", 0)
        if t - last >= 20 * 60 and _online(st):
            _say(st, "dream", random.choice(["……（翻身）", "嗯…再睡五分钟", "梦里也在跑测试"]), "dream")
            out["said"].append("dream")
            _save(st)
        return out

    if not _online(st) and not force:
        out["skipped"].append("没有端在线 ⇒ 先说不了，等端连上再补")
        return out

    # ① 待办提醒
    for td in st.get("todos", []):
        if td.get("done") or not td.get("due"):
            continue
        gap = due_gap(float(td["due"]), t)
        if gap is None:
            continue
        key = "todo:%s" % td["id"]
        if t - st.get("last_said", {}).get(key, 0) >= gap:
            left = float(td["due"]) - t
            when = ("还有 %d 分钟" % int(left // 60)) if left > 0 else \
                   ("已经过期 %d 小时" % int((-left) // 3600))
            _say(st, "todo", "%s（%s）" % (td["text"], when), key)
            out["said"].append(key)

    # ② 自己找活干（没有到点待办时也主动）
    for kind, every, text in INITIATIVES:
        key = "ini:%s" % kind
        if t - st.get("last_initiative", {}).get(key, 0) >= every:
            _say(st, "initiative", text, key)
            st.setdefault("last_initiative", {})[key] = t
            out["said"].append(key)

    _save(st)
    return out


def pull(limit: int = 10) -> dict:
    """页面来取未读的话（取过就删，避免重复念）。"""
    if not FEED.is_file():
        return {"ok": True, "items": []}
    lines = FEED.read_text(encoding="utf-8").splitlines()
    items, keep = [], []
    for line in lines:
        if not line.strip():
            continue
        if len(items) < limit:
            try:
                items.append(json.loads(line))
            except Exception:                                      # noqa: BLE001
                pass
        else:
            keep.append(line)
    FEED.write_text("\n".join(keep) + ("\n" if keep else ""), encoding="utf-8")
    return {"ok": True, "items": items}


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "tick"
    if cmd == "tick":
        print(json.dumps(tick(), ensure_ascii=False))
    elif cmd == "pull":
        print(json.dumps(pull(), ensure_ascii=False))
    elif cmd == "list":
        print(json.dumps(todo_list(), ensure_ascii=False))
    elif cmd == "add":
        print(json.dumps(todo_add(sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else None),
                         ensure_ascii=False))
    elif cmd == "sleep":
        print(json.dumps(set_sleep(sys.argv[2] == "1"), ensure_ascii=False))
    else:
        print(json.dumps({"usage": "proactive.py [tick|pull|list|add <text> [due_ts]|sleep 0|1]"},
                         ensure_ascii=False))
