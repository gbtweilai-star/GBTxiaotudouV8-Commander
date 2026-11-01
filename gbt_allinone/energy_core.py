# -*- coding: utf-8 -*-
"""能源核心（energy_core）：**本机 7.6B 权重 = 她唯一的一块电池**。

主人 2026-11-01（逐字）：「其实你要把她想简单一点，你把本地算力比喻成能源核心，
把能源核心放到大脑执行层为大脑提供源源不断的能源，所有的一切都将明了」。

## 为什么这样最简单

之前每个能力各自接头：`commander` 直连引擎、`trunk_reason` 自己拼 prompt、
覆盖率脚本自己排队 —— 于是**三个客户端抢一块电池**，实测出现过 600s 超时。
一旦把它想成**电池**，问题立刻变成一句话：

    谁用电 → 找能源核心 → 核心排队分配 → 用完记账

于是本模块只做四件事（别的都不做）：

1. **取电口 `think()`**：所有需要推理的地方（大脑执行层、推理环、路由）都走这一个口；
2. **排队 `_bus()`**：跨进程文件锁 —— 一块电池一次只喂一个请求，后来的**排队等待**，
   不再互相把对方拖到超时；
3. **电表 `meter()`**：每次取电记 prompt/completion token、耗时、等待时长，
   落 `state/energy-ledger.jsonl`（花了多少电，可查）；
4. **电量状态 `status()`**：在不在、多重、现在忙不忙、队列里几个、够不够这一刀。

## 边界

- 没电（引擎不在）⇒ `think()` 返回 `ok=False, error="没电"`，**不许假装想过**；
- 排队超时 ⇒ 如实报 `busy_timeout` 并告诉调用方"等不到电"，由调用方降级（规则表兜底）；
- 本模块**不缓存语义结果**、不改 prompt —— 只做"供电 + 记账"。
"""
from __future__ import annotations

import json
import os
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "state" / "energy-ledger.jsonl"
LOCK = ROOT / "state" / "core.lock"
WAIT_DEFAULT = 240.0        # 排队最长等这么久（一块电池喂一次要 15–40s）
STALE_S = 600.0             # 锁文件超过这么久 = 上一个持锁者崩了

# ── 熔断器（蒸馏自 GBT-Framework v5 的 circuit_breaker，只取"状态机"这一个点）──
# 为什么我们需要：引擎挂掉时，每次 think() 都要等 300s 超时才发现 —— 40 个触手就是 40 次白等。
# 熔断后直接秒回 circuit_open，冷却后再放一个探测请求（HALF_OPEN），成功才恢复供电。
BREAKER = ROOT / "state" / "energy-breaker.json"
BREAK_THRESHOLD = 3         # 窗口内失败几次就跳闸
BREAK_WINDOW_S = 60.0       # 统计窗口
BREAK_OPEN_S = 30.0         # 跳闸后冷却多久再放探测


def _breaker_load() -> dict:
    try:
        return json.loads(BREAKER.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"failures": [], "state": "closed", "opened_at": 0.0, "trips": 0}


def _breaker_save(b: dict) -> None:
    try:
        BREAKER.parent.mkdir(parents=True, exist_ok=True)
        BREAKER.write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def breaker_state() -> dict:
    """当前熔断状态（给 status 用）：closed / open / half_open。"""
    b = _breaker_load()
    now = time.time()
    if b.get("state") == "open" and now - float(b.get("opened_at") or 0) >= BREAK_OPEN_S:
        b["state"] = "half_open"
        _breaker_save(b)
    return b


def breaker_allow() -> tuple:
    """能不能发这一次请求：(allow, 原因)。open 且未到冷却 ⇒ 直接拒。"""
    st = breaker_state()
    state = st.get("state") or "closed"
    if state == "open":
        left = max(0.0, BREAK_OPEN_S - (time.time() - float(st.get("opened_at") or 0)))
        return False, "circuit_open（冷却剩 %.0fs；连续失败 %d 次）" % (left, len(st.get("failures") or []))
    return True, state


def breaker_record(ok: bool) -> dict:
    """结果记账：成功即闭合；窗口内失败够了就跳闸。"""
    b = _breaker_load()
    now = time.time()
    if ok:
        b.update({"state": "closed", "failures": [], "opened_at": 0.0})
        _breaker_save(b)
        return b
    fails = [t for t in (b.get("failures") or []) if now - float(t) <= BREAK_WINDOW_S]
    fails.append(now)
    b["failures"] = fails
    if len(fails) >= BREAK_THRESHOLD:
        b["state"] = "open"
        b["opened_at"] = now
        b["trips"] = int(b.get("trips") or 0) + 1
    _breaker_save(b)
    return b



def _engine() -> dict:
    """电池在不在 + 输出功率（tok/s 用最近 20 次取电估）。"""
    from .tentacle import commander as C
    try:
        w = C.weights()
        alive = bool(C.alive(timeout=1.0).get("ok"))
    except Exception as e:  # noqa: BLE001
        return {"alive": False, "error": "%s: %s" % (type(e).__name__, str(e)[:80])}
    return {"alive": alive, "endpoint": C.endpoint(),
            "weights": w.get("name"), "size_gb": w.get("size_gb")}


def _slots() -> int:
    """电池有几个取电口：读 llama-server /props 的 total_slots，读不到就按 4。

    主人 2026-11-01：「触手是干嘛的？谁需要就有独立触手链接能源，透过权重本身就已经和触手
    融合就是天然的分发」—— 引擎本来就是多槽位（实测 total_slots=4），
    所以**不该用一把全局锁把 4 个取电口锁成 1 个**；每个触手各拿一个口。
    """
    try:
        import json as _j
        import urllib.request as _u
        with _u.urlopen("http://127.0.0.1:8792/props", timeout=2) as r:
            n = int((_j.loads(r.read().decode()) or {}).get("total_slots") or 4)
        return max(1, min(8, n))
    except Exception:  # noqa: BLE001
        return 4


class _Port:
    """**一个取电口**（不是全局锁）：谁需要谁占一个空口，用完立刻还。"""

    def __init__(self, wait: float = WAIT_DEFAULT, slots: int | None = None):
        self.wait = float(wait)
        self.slots = int(slots or _slots())
        self.idx = None
        self.waited_ms = 0

    def __enter__(self):
        t0 = time.time()
        LOCK.parent.mkdir(parents=True, exist_ok=True)
        while True:
            for i in range(self.slots):
                f = LOCK.with_name("core.%d.lock" % i)
                try:
                    fd = os.open(str(f), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                    os.write(fd, str(os.getpid()).encode())
                    os.close(fd)
                    self.idx = i
                    self.waited_ms = int((time.time() - t0) * 1000)
                    return self
                except FileExistsError:
                    # 持口者崩了 ⇒ 清臭锁（否则少一个口）
                    try:
                        if time.time() - f.stat().st_mtime > STALE_S:
                            f.unlink(missing_ok=True)
                            continue
                    except OSError:
                        pass
            if time.time() - t0 > self.wait:
                self.waited_ms = int((time.time() - t0) * 1000)
                raise TimeoutError("排队等电超时：%.0fs（%d 个取电口都占着）" % (self.wait, self.slots))
            time.sleep(0.25)

    def __exit__(self, *exc):
        if self.idx is not None:
            try:
                LOCK.with_name("core.%d.lock" % self.idx).unlink(missing_ok=True)
            except OSError:
                pass
        return False


def think(messages: list, *, temperature: float = 0.0, max_tokens: int = 220,
          timeout: float = 300.0, wait: float = WAIT_DEFAULT, label: str = "",
          context: str | None = None, window_chars: int = 0) -> dict:
    """**唯一取电口**：接环形上下文 → 占一个取电口 → 调本机权重 → 记账。

    `context="名字"` 时走**无限制上下文**（`llm/ring_context`）：
      推入 → 有界窗口（恒定长度）给模型看 → 挤出即落 sqlite（不丢）→ 随时 recall 秒查。
    这是主人 2026-11-01 说的「无限制上下文」：**不是把 ctx 调大，是模型只看一屏、全量可查**。
    """
    t0 = time.time()
    allowed, why = breaker_allow()
    if not allowed:
        return {"ok": False, "error": why, "breaker": breaker_state(),
                "waited_ms": 0, "ms": int((time.time() - t0) * 1000),
                "note": "熔断中：引擎连续失败，先不白等；冷却后自动放探测"}
    if not _engine().get("alive"):
        breaker_record(False)
        return {"ok": False, "error": "没电：本机引擎不在", "waited_ms": 0, "context": context and {"name": context},
                "ms": int((time.time() - t0) * 1000)}
    from .tentacle import commander as C
    ctx_info = None
    rc = None
    if context:
        try:
            from .llm import ring_context as RC
            rc = RC.RingContext(name=str(context),
                                window_chars=int(window_chars or RC.DEFAULT_WINDOW_CHARS))
            for m in messages:
                rc.push(str(m.get("role") or "user"), str(m.get("content") or ""))
            messages = rc.window(system="")      # ← 有界窗口（恒定长度）
            st = rc.stats()
            ctx_info = {"name": str(context), "window_items": len(messages),
                        "window_chars": sum(len(m.get("content") or "") for m in messages),
                        "seq": st.get("seq"), "db_turns": st.get("db_turns"),
                        "budget": rc.window_chars}
        except Exception as e:  # noqa: BLE001
            ctx_info = {"name": str(context), "error": "%s: %s" % (type(e).__name__, str(e)[:100])}
    try:
        with _Port(wait=wait) as bus:
            t_call = time.time()
            r = C.ask(messages, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
            used_ms = int((time.time() - t_call) * 1000)
            waited_ms = bus.waited_ms
            port = bus.idx
    except TimeoutError as e:
        rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "label": label[:60],
               "ok": False, "error": "busy_timeout", "detail": str(e)[:120],
               "waited_ms": int((time.time() - t0) * 1000)}
        _log(rec)
        return {"ok": False, "error": "busy_timeout：" + str(e), "waited_ms": rec["waited_ms"],
                "ms": rec["waited_ms"]}
    usage = r.get("usage") or {}
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "label": label[:60], "port": port,
           "ok": bool(r.get("ok")), "error": None if r.get("ok") else str(r.get("error"))[:120],
           "prompt_tokens": usage.get("prompt_tokens"),
           "completion_tokens": usage.get("completion_tokens"),
           "port": port, "waited_ms": waited_ms, "used_ms": used_ms,
           "ms": int((time.time() - t0) * 1000)}
    try:
        breaker_record(bool(r.get("ok")))
    except Exception:  # noqa: BLE001
        pass
    _log(rec)
    if rc is not None and r.get("ok"):
        try:
            rc.push("assistant", str(r.get("text") or "")[:4000])
            if ctx_info is not None:
                ctx_info["window_items_after"] = len(rc.window(system=""))
        except Exception:  # noqa: BLE001
            pass
    out = {"ok": bool(r.get("ok")), "text": r.get("text"), "error": r.get("error"),
           "usage": usage, "port": port, "waited_ms": waited_ms, "used_ms": used_ms,
           "ms": rec["ms"], "label": label, "context": ctx_info}
    return out


def _log(rec: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def meter(limit: int = 200) -> dict:
    """电表：最近 N 次取电的总量、功率、等待。"""
    rows = []
    if LEDGER.exists():
        with LEDGER.open(encoding="utf-8") as fh:
            for line in fh:
                try:
                    rows.append(json.loads(line))
                except Exception:  # noqa: BLE001
                    continue
    recent = rows[-limit:]
    ok = [r for r in recent if r.get("ok")]
    pt = sum(int(r.get("prompt_tokens") or 0) for r in ok)
    ct = sum(int(r.get("completion_tokens") or 0) for r in ok)
    used = sum(int(r.get("used_ms") or 0) for r in ok)
    waited = sum(int(r.get("waited_ms") or 0) for r in ok)
    return {"ok": True, "calls": len(recent), "calls_ok": len(ok),
            "failed": len(recent) - len(ok),
            "prompt_tokens": pt, "completion_tokens": ct,
            "avg_ms": int(used / len(ok)) if ok else 0,
            "power_tok_s": round(ct / (used / 1000.0), 2) if used else None,
            "waited_s_total": round(waited / 1000.0, 1),
            "排队占比": round(waited / (used + waited), 3) if (used + waited) else 0,
            "口径": "一块电池：先排队再取电；排队时长单列，不算进功率"}


def status(wait: float = 0.0) -> dict:
    """电量状态：在不在、忙不忙、排队里几个、刚花过多少电。"""
    eng = _engine()
    busy = LOCK.exists()
    q = 0
    try:
        if busy:
            q = 1
    except OSError:
        pass
    m = meter(limit=20)
    return {"ok": bool(eng.get("alive")), "core": eng, "ports": _slots(),
            "in_use": sum(1 for i in range(_slots()) if LOCK.with_name("core.%d.lock" % i).exists()),
            "busy": busy, "queue": q,
            "breaker": breaker_state(),
            "recent": {"calls": m["calls"], "avg_ms": m["avg_ms"],
                       "power_tok_s": m["power_tok_s"], "waited_s_total": m["waited_s_total"]},
            "note": "本机权重是唯一电池；所有推理都从 energy_core.think() 取电"}


def breaker_reset() -> dict:
    """手动复位熔断器（排障后跑一次）。"""
    b = {"failures": [], "state": "closed", "opened_at": 0.0, "trips": 0}
    _breaker_save(b)
    return {"ok": True, "breaker": b}


def breaker_trip(reason: str = "manual") -> dict:
    """手动跳闸（测试/演练用）。"""
    b = breaker_record(False)
    b.update({"state": "open", "opened_at": time.time(),
              "trips": int(b.get("trips") or 0) + 1})
    _breaker_save(b)
    return {"ok": True, "breaker": b, "reason": reason}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    if op == "status":
        return status()
    if op == "meter":
        return meter(limit=int(kw.get("limit") or 200))
    if op == "breaker":
        sub = str(kw.get("do") or "status").lower()
        if sub == "status":
            return {"ok": True, "breaker": breaker_state()}
        if sub == "reset":
            return breaker_reset()
        if sub == "trip":
            return breaker_trip(str(kw.get("reason") or "manual"))
        return {"ok": False, "error": "breaker 不认 do=%s（status/reset/trip）" % sub}
    return {"ok": False, "error": "energy_core 只供 think/status/meter/breaker（op=%s）" % op}
