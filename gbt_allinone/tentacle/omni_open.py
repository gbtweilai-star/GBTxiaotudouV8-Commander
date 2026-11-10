# -*- coding: utf-8 -*-
"""万能插·自动识别插口 + 自动配备插上（omni_open）。

主人令 2026-11-01（修正）：
  「万能插有自动识别插口，自动配备插上，而不是固定的六插口」

## 这一版和上一版的差别（上一版错在哪）

上一版把插座写成**固定六类**（process/file/api/web/app/ai）——那是"插座能源"分类，
不是"墙上到底有几个洞"。主人要的是：**先看墙上有哪些洞（自动识别），再把该插的都插上（自动配备）**。

现在的做法：

    ① 识别：`omni_plug.discover()` 现读可插面 —— 监听端口 / 本地模型口 / 本地DB /
            命令行软件 / 窗口 / 串口 / 进程；
    ② 配备：把每个可插面翻成一根 `Socket(kind, target)`，用 `Pulse().plug()` **真插上**；
    ③ 落账：`state/omni_open.json` 记「哪类插头几根、插在哪、依据是什么、什么时候扫的」；
    ④ 自动：`api._run_task_core_body` 分派前调 `ensure()` —— 缓存过期就**后台重扫**，
            绝不阻塞调用（全量 discover 实测 26.1s，挂在主路上会把框架拖死）。

## 三条口径

1. **种类不是写死的**：`kinds` 由这一轮**发现了什么**决定（端口→`api`、模型口→`ai`、
   DB/文件→`file`、命令行软件→`process`、窗口→`app`、串口→`device`），发现不到就没有那一类。
2. **不许假插**：`discover` 报 `not_listening` 的（比如本机没起 ollama），照样登记，但标
   `ok=False` 与原因 —— **登记 ≠ 已连上**。
3. **不阻塞**：`ensure()` 只读快照；重扫在后台线程里做，扫完原子替换快照。

## op
  status  上一轮快照 + 是否正在扫（只读、秒回）
  scan    立刻扫一遍（同步，26s 左右；给"我要现在看到"用）
  ensure  触发一次后台重扫（force 时忽略 TTL）
"""
from __future__ import annotations

import json
import os
import pathlib
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "state" / "omni_open.json"
TTL = 300.0                 # 快照寿命：5 分钟
_LOCK = threading.Lock()
_SCAN_STATE = {"running": False, "started_at": None, "last_error": None}


def _load() -> dict:
    try:
        return json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _save(d: dict) -> None:
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    tmp = SNAPSHOT.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, SNAPSHOT)


# 可插面 → 插头类型（**由发现决定，不预置清单**）。
# `plug_kind` 是万能插能源模型里能真插的那几类（SOCKET_KINDS）；对不上就"识别到、未插"并写明。
_SURFACE_KIND = {
    "监听端口": ("port", "api"),
    "本地模型口": ("ai", "ai"),
    "本地DB": ("file", "file"),
    "命令行软件": ("process", "process"),
    "窗口": ("app", "app"),
    "串口": ("serial", None),
}


def _kind_of(surface: str, item) -> tuple:
    return _SURFACE_KIND.get(surface, ("unknown", None))


def _target_of(surface: str, item) -> str:
    # 🔴 2026-11-09 根因修复（红黄警报 socket.alert 永远清不掉）：
    #   discover 的 sample 是**混合类型** —— 实测「窗口」列表里混着字符串元素，
    #   而这里一律按 dict 调 item.get(...) ⇒ AttributeError: 'str' object has no attribute 'get'
    #   ⇒ scan() 在 _rows_from_discover 处整轮崩掉（第 141 行不在 try 内）
    #   ⇒ state/omni_open.json 的快照停在旧一轮 ⇒ alerts 的 socket.alert 永久为真。
    #   口径：能认 dict 就按字段取，认不出就如实把它当字符串目标。
    if surface == "监听端口":
        if not isinstance(item, dict):
            return str(item)
        addr = str(item.get("addr") or "127.0.0.1")
        if addr in ("0.0.0.0", "::", "[::]", ""):
            addr = "127.0.0.1"          # 通配地址不能当客户端目标
        return "%s:%s" % (addr, item.get("port"))
    if surface == "本地模型口":
        return str(item.get("base") or "") if isinstance(item, dict) else str(item)
    if surface == "本地DB":
        return str(item)
    if surface == "命令行软件":
        return str(item)
    if surface == "窗口":
        if not isinstance(item, dict):
            return str(item)
        return str(item.get("title") or item.get("hwnd") or item)
    return str(item)


def _rows_from_discover(d: dict) -> tuple[list, dict]:
    """把 discover 的读数翻成「一根根插头」。返回 (插头清单, 发现面计数)。"""
    plugs: list[dict] = []
    counts: dict[str, int] = {}

    def _take(surface: str, items):
        n = 0
        for it in items or []:
            kind, plug_kind = _kind_of(surface, it)
            target = _target_of(surface, it)
            if not target:
                continue
            ok = True
            reason = ""
            if isinstance(it, dict):
                if it.get("ok") is False:
                    ok, reason = False, str(it.get("未读到") or it.get("kind") or "未连上")
                elif it.get("ok") is True:
                    ok = True
            plugs.append({"surface": surface, "kind": kind, "plug_kind": plug_kind,
                          "target": target[:200], "ok": ok, "reason": reason[:120]})
            n += 1
        counts[surface] = n

    ports = (d.get("监听端口") or {}).get("sample") or []
    _take("监听端口", ports)
    _take("本地模型口", d.get("本地模型口") or [])
    _take("本地DB", d.get("本地DB") or [])
    tools = d.get("命令行软件") or {}
    _take("命令行软件", [k for k, v in tools.items() if v] if isinstance(tools, dict)
          else [t for t in tools if t])
    _take("窗口", (d.get("窗口") or {}).get("sample") or [])
    _take("串口", d.get("串口") or [])
    counts["进程"] = int((d.get("进程") or {}).get("count") or 0)
    return plugs, counts


def scan(deep: bool = False) -> dict:
    """同步扫一遍：识别可插面 → 配上插头 → 落账。≈26s（这是它的真实成本，不藏）。"""
    t0 = time.time()
    try:
        from .. import omni_plug as O
        d = O.discover(deep=deep)
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, str(e)[:160])}
    plugs, counts = _rows_from_discover(d)

    # **自动配备插上**：每根插头真过一遍 Pulse.plug（Pulse 只管登记与快照，不执行动作）
    plugged, failed = 0, []
    try:
        pulse = O.Pulse()
        for p in plugs:
            if not p.get("plug_kind"):
                failed.append({"target": p["target"], "error": "该类插头不在能源模型里（已识别、未插）"})
                continue
            try:
                pulse.plug(O.Socket(p["plug_kind"], p["target"]))
                plugged += 1
            except Exception as e:  # noqa: BLE001
                failed.append({"target": p["target"], "error": "%s: %s" % (type(e).__name__, str(e)[:80])})
    except Exception as e:  # noqa: BLE001
        failed.append({"target": "*", "error": "%s: %s" % (type(e).__name__, str(e)[:80])})

    kinds: dict[str, int] = {}
    for p in plugs:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1

    # 增量对比：**墙上的洞变了要立刻知道**（新插口 / 拔掉的 / 通断翻转）
    old = _load()
    diff = _diff(old, plugs)
    hist = list(old.get("history") or [])[-9:]
    if diff.get("added") or diff.get("removed") or diff.get("flipped"):
        hist.append({"at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                     "added": len(diff["added"]), "removed": len(diff["removed"]),
                     "flipped": len(diff["flipped"])})

    snap = {
        "ok": True, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "scan_s": round(time.time() - t0, 1),
        "发现面": counts, "kinds": kinds, "插头数": len(plugs), "已插": plugged,
        "未连上": sum(1 for p in plugs if not p["ok"]),
        "plugs": plugs[:200], "plug失败": failed[:20],
        "diff": diff, "history": hist,
        "口径": "种类由本轮发现决定，不写死；登记 ≠ 已连上（ok=False 带原因）；Pulse 只登记不执行；"
                "增量对比以 (kind,target) 为键，拔掉的插口必须报警",
        "counts": {"kinds": len(kinds), "plugs": len(plugs), "plugged": plugged},
    }
    _save(snap)
    return snap


def _key(p: dict) -> tuple:
    return (str(p.get("kind")), str(p.get("target")))


def _diff(old: dict, plugs: list) -> dict:
    """上一轮快照 vs 这一轮发现：新增 / 拔掉 / 通断翻转。**纯函数，可离线测**。"""
    if not old:
        return {"added": [], "removed": [], "flipped": [], "first_scan": True}
    old_map = {_key(p): p for p in (old.get("plugs") or [])}
    new_map = {_key(p): p for p in plugs}
    added = [new_map[k] for k in new_map.keys() - old_map.keys()]
    removed = [old_map[k] for k in old_map.keys() - new_map.keys()]
    flipped = [{"kind": new_map[k].get("kind"), "target": new_map[k].get("target"),
                "was": old_map[k].get("ok"), "now": new_map[k].get("ok")}
               for k in new_map.keys() & old_map.keys()
               if bool(old_map[k].get("ok")) != bool(new_map[k].get("ok"))]
    return {"added": added[:50], "removed": removed[:50], "flipped": flipped[:50],
            "counts": {"added": len(added), "removed": len(removed), "flipped": len(flipped)},
            "alert": bool(removed) or bool(flipped),
            "first_scan": False}



def _scan_bg(force: bool = False) -> bool:
    """后台重扫一次；已经在扫就不重复起。"""
    with _LOCK:
        if _SCAN_STATE["running"]:
            return False
        _SCAN_STATE["running"] = True
        _SCAN_STATE["started_at"] = time.time()

    def _run():
        try:
            scan()
            _SCAN_STATE["last_error"] = None
        except Exception as e:  # noqa: BLE001
            _SCAN_STATE["last_error"] = "%s: %s" % (type(e).__name__, str(e)[:160])
        finally:
            with _LOCK:
                _SCAN_STATE["running"] = False

    threading.Thread(target=_run, name="omni_open_scan", daemon=True).start()
    return True


def ensure(force: bool = False) -> dict:
    """**调用前自动执行的一步**：只读快照（秒回）；过期就在后台重扫，绝不阻塞调用。"""
    snap = _load()
    age = None
    if snap.get("at"):
        try:
            age = time.time() - time.mktime(time.strptime(snap["at"], "%Y-%m-%dT%H:%M:%S"))
        except Exception:  # noqa: BLE001
            age = None
    stale = force or age is None or age > TTL
    triggered = False
    if stale:
        triggered = _scan_bg(force)
    return {"ok": True, "cached": not triggered, "scanning": _SCAN_STATE["running"],
            "age_s": round(age, 1) if age is not None else None,
            "kinds": snap.get("kinds") or {}, "插头数": snap.get("插头数"),
            "发现面": snap.get("发现面") or {}, "at": snap.get("at"),
            "口径": "种类由发现决定；快照 5 分钟一换；重扫在后台，不挡调用"}


def status() -> dict:
    e = ensure()
    snap = _load()
    d = snap.get("diff") or {}
    return {"ok": True, "kinds": e.get("kinds"), "插头数": e.get("插头数"),
            "diff": {"counts": d.get("counts"), "alert": bool(d.get("alert"))},
            "history_tail": (snap.get("history") or [])[-3:],
            "发现面": e.get("发现面"), "at": e.get("at"), "age_s": e.get("age_s"),
            "scanning": e.get("scanning"), "scan_s": snap.get("scan_s"),
            "sample": (snap.get("plugs") or [])[:12],
            "口径": e.get("口径")}


def run(op: str = "status", **kw) -> dict:
    op = str(op or "status").lower()
    if op == "status":
        return status()
    if op == "scan":
        return scan(deep=bool(kw.get("deep")))
    if op == "ensure":
        return ensure(force=bool(kw.get("force")))
    if op == "diff":
        d = _load().get("diff") or {}
        return {"ok": True, "diff": d, "at": _load().get("at"),
                "alert": bool(d.get("alert")),
                "口径": "以 (kind,target) 为键；拔掉/通断翻转会 alert"}
    if op == "history":
        return {"ok": True, "history": _load().get("history") or []}
    return {"ok": False, "error": "omni_open 不认 op=%s（status/scan/ensure/diff/history）" % op}
