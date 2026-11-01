# -*- coding: utf-8 -*-
"""上下文守卫（context_guard）：把 `tools/context_guard.py` 正式**接成能力位**。

主人 2026-11-01（逐字）：「我设计了无数原生能力，有些估计压根你就没给我部署上去过」。

## 实测到的缺口（这就是那句话的证据）

| 件 | 源码里有 | 登记为能力位 | 接进对话路径 |
|---|---|---|---|
| `llm/ring_context`（无限制上下文：有界窗口 + 溢出落库 + 秒查） | ✅ | ✅ | ❌ **原来没接**（本轮接进 `energy_core.think(context=…)`） |
| `tools/context_guard.py`（实时异常检测 + 回大脑 + 纠正） | ✅ 18.2 KB | ❌ **没登记** | ❌ 只在命令行里跑 |
| `tentacle_bind`（双向绑定） | ✅ | ✅ | 半 |

本模块只做一件事：**把现有 `context_guard` 的函数包成能力位**（不复制逻辑、不改它的判据），
并提供"双插"账本：`op=bind` 把某根触手/能力位钉到某个环形上下文上，
`op=bindings` 列出来 —— 这样"上下文↔触手"是**双向可查**的，而不是口头说绑了。

## op
    status    环读数 + 异常诊断（调用 guard.sample/diagnose）
    tick      跑一拍：采样 → 诊断 → （可选）回大脑 → 纠正
    bind      {"tentacle": "...", "context": "..."} 双插：落 state/context-bindings.json
    bindings  列出全部双插
    bind_guard 把"溢出保护触手"绑上（调用 guard.bind_tentacle）
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
GUARD = ROOT / "tools" / "context_guard.py"
BINDINGS = ROOT / "state" / "context-bindings.json"
STATE = ROOT / "state" / "context-guard.json"


def _guard():
    """按文件路径加载 tools/context_guard.py（它是脚本，不在包里）。"""
    spec = importlib.util.spec_from_file_location("gbt_context_guard", str(GUARD))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def _ring(name: str = "default"):
    g = _guard()
    return g, g._ring(name)


def status(name: str = "default") -> dict:
    g, rc = _ring(name)
    s = g.sample(rc)
    diag = []
    try:
        prev = json.loads(STATE.read_text(encoding="utf-8"))
        diag = g.diagnose(s, prev.get("sample"), int(prev.get("streak") or 0))
    except Exception:  # noqa: BLE001
        diag = g.diagnose(s, None, 0)
    return {"ok": True, "ring": name, "sample": s, "anomalies": diag,
            "guard": str(GUARD), "口径": "实时异常 = 窗口/溢出/落库三项；异常直接给大脑"}


def tick(name: str = "default", do_correct: bool = True) -> dict:
    g, rc = _ring(name)
    prev, streak = None, 0
    if STATE.exists():
        try:
            d = json.loads(STATE.read_text(encoding="utf-8"))
            prev, streak = d.get("sample"), int(d.get("streak") or 0)
        except Exception:  # noqa: BLE001
            pass
    rec = g.tick(rc, prev, streak, do_correct=do_correct)
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                 "sample": rec.get("sample") or rec,
                                 "streak": rec.get("streak") or 0},
                                ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "ring": name, "tick": rec}


def bind(tentacle: str, context: str) -> dict:
    """双插：触手 ↔ 上下文，双向可查。"""
    BINDINGS.parent.mkdir(parents=True, exist_ok=True)
    try:
        d = json.loads(BINDINGS.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        d = {"at": "", "pairs": []}
    pairs = [p for p in (d.get("pairs") or []) if p.get("tentacle") != tentacle]
    pairs.append({"tentacle": tentacle, "context": context,
                  "at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    d = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "pairs": pairs}
    BINDINGS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"ok": True, "bound": {"tentacle": tentacle, "context": context},
            "total": len(pairs), "file": str(BINDINGS)}


def bindings() -> dict:
    try:
        d = json.loads(BINDINGS.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        d = {"pairs": []}
    return {"ok": True, "pairs": d.get("pairs") or [], "total": len(d.get("pairs") or []),
            "口径": "双插账本：哪根触手钉在哪个环上；一条触手只能钉一个环（重绑会覆盖）"}


def bind_guard() -> dict:
    g = _guard()
    try:
        r = g.bind_tentacle()
    except Exception as e:  # noqa: BLE001
        r = {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:120])}
    return {"ok": bool(r.get("ok", True)), "result": r,
            "note": "把'上下文溢出保护触手'绑上（源码原本就有这个函数，只是没接成能力位）"}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    name = str(kw.get("name") or "default")
    if op == "status":
        return status(name)
    if op == "tick":
        return tick(name, do_correct=bool(kw.get("do_correct", True)))
    if op == "bind":
        return bind(str(kw.get("tentacle") or ""), str(kw.get("context") or ""))
    if op == "bindings":
        return bindings()
    if op == "bind_guard":
        return bind_guard()
    return {"ok": False, "error": "context_guard 不认 op=%s（status/tick/bind/bindings/bind_guard）" % op}
