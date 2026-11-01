# -*- coding: utf-8 -*-
"""引擎激活闸门（唯一判定）—— 重建版（2026-11-01 补齐）。

## 为什么有这个文件
`tools/codex-scripts/keep-warm.py` 只 `from _engine_gate import decide, health`，
但**该文件从未随仓库发布**（全仓 0 文件，上游 main 逐路径实测 404）。
2026-11-01 按 `keep-warm.py` 头部写明的判据补回：

  · `health(base, key)`：只读 `GET {base}/health`（不占 worker、不排队），
    返回带 `_ok` / `_ms` / `_err` 的读数（RunPod 形状：`workers.ready/initializing`、
    `jobs.inQueue/completed/failed`；llama.cpp 形状只有 `{"status":"ok"}`，一并兼容）。
  · `decide(h)`：**唯一判定**——
      ready/initializing > 0            ⇒ 发（那才叫保温）；
      全零且有积压（inQueue > 0）        ⇒ **不发**（发了只是把积压推高）；
      全零且无积压                       ⇒ 发一条唤醒 worker（否则永远冷着）；
      health 读不到                      ⇒ **不发**，把原因原样交给调用方写日志。

本文件是**重建件**，不是原作者原文；判定只实现 `keep-warm.py` 头部的四条。
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

__all__ = ["health", "decide"]

_UA = "GBTxiaotudouV8-keepwarm/1.0"


def health(base: str, key: str, timeout: float = 10.0) -> dict:
    """只读 `/health`。返回 dict（总带 `_ok` / `_ms`；失败带 `_err`、不抛）。"""
    base = (base or "").strip().rstrip("/")
    if not base:
        return {"_ok": False, "_ms": 0, "_err": "缺 base"}
    req = urllib.request.Request(
        base + "/health",
        headers={"Authorization": "Bearer " + (key or ""), "User-Agent": _UA},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
        ms = int((time.time() - t0) * 1000)
        try:
            data = json.loads(raw or b"{}")
        except ValueError:
            data = {"status": raw[:200].decode("utf-8", "replace")}
        if not isinstance(data, dict):
            data = {"status": data}
        data["_ok"] = True
        data["_ms"] = ms
        return data
    except urllib.error.HTTPError as exc:
        return {"_ok": False, "_ms": int((time.time() - t0) * 1000),
                "_err": "HTTP %s" % exc.code}
    except Exception as exc:  # noqa: BLE001  —— 读不到就如实报，不抛
        return {"_ok": False, "_ms": int((time.time() - t0) * 1000),
                "_err": "%s: %s" % (type(exc).__name__, str(exc)[:120])}


def _int(v) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


def decide(h: dict) -> tuple[bool, str]:
    """按 `/health` 读数决定这一轮**发不发**保温请求。返回 `(send, why)`。"""
    h = h or {}
    if not h.get("_ok"):
        return False, "health 读不到：%s" % (h.get("_err") or "未知原因")
    workers = h.get("workers") if isinstance(h.get("workers"), dict) else {}
    jobs = h.get("jobs") if isinstance(h.get("jobs"), dict) else {}
    ready = _int(workers.get("ready"))
    init = _int(workers.get("initializing"))
    inq = _int(jobs.get("inQueue"))
    if ready > 0 or init > 0:
        return True, "有 worker（ready=%d init=%d）" % (ready, init)
    if inq > 0:
        return False, "全零但队列在堆（inQueue=%d）—— 保温只会加积压" % inq
    return True, "全零且无积压 —— 发一条唤醒 worker"
