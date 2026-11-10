# -*- coding: utf-8 -*-
"""编排账本（orchestration）：**扫了哪里、改了什么、新增什么，全部一条一条记账**。

主人 2026-11-01（逐字）：「不管扫描哪里，修改哪里，新增什么都要在编排账本里面有记录，
这样重启时候看一遍编排面板就一目了然了」。

## 为什么要独立一本账

`store/audit.jsonl` 记的是**每次调用**（含 probe、含被拒），是流水不是编排；
重启后想知道"上一轮到底动过什么、新增了哪些能力位、哪些文件被改过"，翻流水等于大海捞针。

所以这本账只记**编排动作**（六类）：

    scan    扫描（覆盖/自检/反查/插口/器官…）
    add     新增（能力位/文件/账本/工具）
    edit    修改（注册表/分派/策略/文档/代码）
    deploy  部署（登记 + 分派 + 快照）
    fix     修复（回滚/改正/补丁）
    run     运行（判决/推理/吞食等有产出的执行）

每条：时间 · 会话 · 动作 · 对象 · 摘要 · 结果 · 证据（文件/命令/读数）。

## 面板（重启后先看这个）

`op=panel` 一次给出：
  · 本次会话（或指定会话）做了什么：按动作分类计数
  · 最近 N 条动作（默认 15）
  · 能力位现状 vs 快照（有没有新增/漂移）
  · 各类扫描的**最后时间**（多久没扫了，一眼看出）
  · 上次看面板的时间（`state/orchestration-seen.json`）⇒ "自上次以来新增了什么"

三条例律：**只追加不改写** · **probe 调用不记**（避免噪音） · **空动作不记**（没对象不写）。
"""
from __future__ import annotations

import json
import os
import pathlib
import threading
import time

# 本文件在 gbt_allinone/orchestration.py ⇒ parents[0]=gbt_allinone，parents[1]=仓库根
ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "state" / "orchestration-ledger.jsonl"

# 同进程多线程并发追加时，`open("a")` 的 buffered write 可能交错成残片
# （2026-11-07 实测账本里出现两段同样的坏字节，位置 38694 / 40155）。
# 锁只防同进程；写入用一次 `os.write`（而不是 buffered 多段 write），
# 跨进程时 NTFS 的 O_APPEND 也尽量保持单次写。读侧另有 errors="replace" 兜底。
_WRITE_LOCK = threading.Lock()
SEEN = ROOT / "state" / "orchestration-seen.json"
ACTIONS = ("scan", "add", "edit", "deploy", "fix", "run")


def _session() -> str:
    """会话标记：进程启动时间（同一次运行内一致；重启即新会话）。"""
    try:
        p = ROOT / "state" / "session.json"
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("pid") == os.getpid():
            return d.get("session") or ""
    except Exception:  # noqa: BLE001
        pass
    s = time.strftime("%Y%m%d-%H%M%S")
    try:
        (ROOT / "state").mkdir(parents=True, exist_ok=True)
        (ROOT / "state" / "session.json").write_text(
            json.dumps({"pid": os.getpid(), "session": s,
                        "started": time.strftime("%Y-%m-%dT%H:%M:%S")}, ensure_ascii=False),
            encoding="utf-8")
    except OSError:
        pass
    return s


def record(action: str, target: str, detail: str = "", result: str = "ok",
           evidence: str = "", actor: str = "gbt") -> dict:
    """记一条编排动作。**空对象不记**（没对象 = 没动作）。"""
    action = str(action or "").strip().lower()
    target = str(target or "").strip()
    if action not in ACTIONS or not target:
        return {"ok": False, "error": "动作必须是 %s 之一且对象不能为空" % (ACTIONS,)}
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "session": _session(),
           "actor": actor[:40], "action": action, "target": target[:200],
           "detail": str(detail)[:400], "result": str(result)[:60],
           "evidence": str(evidence)[:300]}
    line = (json.dumps(rec, ensure_ascii=False) + "\n").encode("utf-8")
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with _WRITE_LOCK:
        fd = os.open(str(LEDGER), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    return {"ok": True, "recorded": rec}


def _rows() -> list:
    out = []
    if LEDGER.exists():
        with LEDGER.open(encoding="utf-8", errors="replace") as fh:
            for line in fh:
                try:
                    out.append(json.loads(line))
                except Exception:  # noqa: BLE001
                    continue
    return out


def panel(limit: int = 15, session: str = "") -> dict:
    """编排面板：重启后先看这个 —— 上次动过什么、还差什么。"""
    rows = _rows()
    sess = session or _session()
    mine = [r for r in rows if r.get("session") == sess]
    by_action = {a: sum(1 for r in mine if r.get("action") == a) for a in ACTIONS}

    last_scan = {}
    for r in rows:
        if r.get("action") == "scan":
            last_scan[r.get("target")] = r.get("at")
    last_scan = dict(sorted(last_scan.items(), key=lambda kv: kv[1] or "", reverse=True)[:8])

    # 能力位 vs 快照（漂移一眼看到）
    caps = snap = None
    try:
        from .caps_registry import BENIGN_CAPS
        caps = len(BENIGN_CAPS)
    except Exception:  # noqa: BLE001
        pass
    try:
        snap = json.loads((ROOT / "data" / "capabilities.json").read_text(encoding="utf-8")).get("count")
    except Exception:  # noqa: BLE001
        pass

    seen_at = ""
    try:
        seen_at = json.loads(SEEN.read_text(encoding="utf-8")).get("at") or ""
    except Exception:  # noqa: BLE001
        pass
    since = [r for r in rows if not seen_at or (r.get("at") or "") > seen_at]

    return {"ok": True, "session": sess,
            "ledger_lines": len(rows), "session_lines": len(mine),
            "by_action": by_action,
            "recent": mine[-limit:][::-1] or rows[-limit:][::-1],
            "last_scan": last_scan,
            "caps": {"registry": caps, "snapshot": snap,
                     "drift": (None if caps is None or snap is None else caps - snap)},
            "since_last_look": {"at": seen_at, "n": len(since),
                                "items": since[-10:][::-1]},
            "口径": "只追加不改写；probe 不记；重启看这一屏就知道上轮动了什么"}


def mark_seen() -> dict:
    """标记"已看过面板"（下一次 panel 的 since_last_look 从此刻算）。"""
    at = time.strftime("%Y-%m-%dT%H:%M:%S")
    SEEN.parent.mkdir(parents=True, exist_ok=True)
    SEEN.write_text(json.dumps({"at": at}, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "seen_at": at}


def status() -> dict:
    rows = _rows()
    return {"ok": True, "ledger_lines": len(rows),
            "last": rows[-1] if rows else None,
            "file": str(LEDGER),
            "口径": "六类动作：scan/add/edit/deploy/fix/run"}


def run(op: str = "panel", **kw) -> dict:
    op = str(op or "panel").lower()
    if op == "record":
        return record(str(kw.get("action") or ""), str(kw.get("target") or ""),
                      str(kw.get("detail") or ""), str(kw.get("result") or "ok"),
                      str(kw.get("evidence") or ""), str(kw.get("actor") or "gbt"))
    if op == "panel":
        return panel(limit=int(kw.get("limit") or 15), session=str(kw.get("session") or ""))
    if op == "seen":
        return mark_seen()
    if op == "status":
        return status()
    return {"ok": False, "error": "orchestration 不认 op=%s（record/panel/seen/status）" % op}
