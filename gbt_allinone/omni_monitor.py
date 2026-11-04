# -*- coding: utf-8 -*-
"""万能插 · 多域监控（2026-11-02）

口径（主人令）：「多域监控就是把一个东西的全面都监控住，哪怕是细微的变化都能发现」。

做法：
  · 每次采样把 7 类插座 + 系统 + 记忆链 + 触手绑定 + 蓝图 + 关键状态文件 + 数字人 全部读一遍；
  · 与上一次采样做**逐字段 diff**（数值给 delta，字符串/布尔给 from→to），
    连 +0.1% 的 CPU、文件 mtime/size、记忆版本 +1、绑定数 ±1 都会进 changes；
  · 变化落 state/omni-monitor.jsonl（追加式台账），保留最近 240 次采样在内存里供页面轮询。
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state"
EVENTS = STATE / "omni-monitor.jsonl"
LOCK = threading.RLock()
HISTORY: list = []
EVENT_RING: list = []
MAX_HISTORY = 240
LAST = {"at": 0.0, "snap": None}


def _psutil():
    try:
        import psutil
        return psutil
    except Exception:  # noqa: BLE001
        return None


def _stat_file(p: Path) -> dict:
    try:
        st = p.stat()
        return {"exists": True, "mtime": round(st.st_mtime, 3), "size": st.st_size}
    except Exception:  # noqa: BLE001
        return {"exists": False, "mtime": 0, "size": 0}


def _sha_short(p: Path, limit: int = 2 * 1024 * 1024) -> str:
    try:
        h = hashlib.sha1()
        with p.open("rb") as f:
            while True:
                b = f.read(65536)
                if not b:
                    break
                h.update(b)
                limit -= len(b)
                if limit <= 0:
                    break
        return h.hexdigest()[:12]
    except Exception:  # noqa: BLE001
        return ""


def _read_json(p: Path, default=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def _count_bindings() -> dict:
    d = _read_json(STATE / "asset_bindings.json", {}) or {}
    pairs = 0
    for row in d.values():
        pairs += len((row or {}).get("tentacles") or [])
    return {"assets": len(d), "pairs": pairs}


def _tentacle_coverage() -> dict:
    try:
        from . import caps_registry as CR
        from . import dh_tentacle as DT  # noqa: F401
    except Exception:  # noqa: BLE001
        CR = None
    d = _read_json(STATE / "asset_bindings.json", {}) or {}
    bound = set()
    for row in d.values():
        for t in (row or {}).get("tentacles") or []:
            bound.add(t)
    out = {"bound": len(bound)}
    if CR is not None:
        caps = list(getattr(CR, "BENIGN_CAPS", {}).keys())
        out["caps_total"] = len(caps)
        out["caps_bound"] = sum(1 for c in caps if c in bound)
        out["caps_missing"] = out["caps_total"] - out["caps_bound"]
    return out


def _memory_state() -> dict:
    try:
        from .tools import memory_sync as MS
        v = MS.version() or {}
        return {"version": v.get("version"), "count": v.get("count"),
                "head": v.get("h"), "at": v.get("at")}
    except Exception as e:  # noqa: BLE001
        return {"error": "%s: %s" % (type(e).__name__, str(e)[:80])}


def _blueprint_state() -> dict:
    d = STATE / "blueprints"
    if not d.is_dir():
        return {"id": "", "approved": False}
    cands = [p for p in d.glob("*.json")
             if not p.name.endswith((".approved.json", ".mindmap.json", ".revise.json", ".stuck.json"))]
    if not cands:
        return {"id": "", "approved": False}
    p = max(cands, key=lambda x: x.stat().st_mtime)
    b = _read_json(p, {}) or {}
    tasks = b.get("tasks") or []
    done = sum(1 for t in tasks if str((t or {}).get("status")) in ("done", "ok"))
    return {"id": p.stem, "tasks": len(tasks), "done": done,
            "approved": (d / (p.stem + ".approved.json")).is_file(),
            "revise": len((_read_json(d / (p.stem + ".revise.json"), {}) or {}).get("items") or [])}


def _dh_state() -> dict:
    try:
        from gbt_allinone import dh_omni_loop as DL
        ctl = DL.CONTROL
        return {"action": ctl.action, "phase": round(time.time() - ctl.started, 3) if ctl.started else 0,
                "err": round(ctl.last_err, 4), "omni": bool((ctl.omni or {}).get("plugged")),
                "hand": (ctl.hand or {}).get("pose") or ""}
    except Exception as e:  # noqa: BLE001
        return {"error": "%s: %s" % (type(e).__name__, str(e)[:80])}


def _omni_domains() -> dict:
    try:
        from . import omni_plug as OP
        from .security import policy as P
        snap = OP.run(op="sockets") or {}
        plugged = snap.get("插着") or {}
        kinds = list(OP.SOCKET_KINDS)
        counts = {k: 0 for k in kinds}
        for v in plugged.values():
            k = str((v or {}).get("kind") or "")
            if k in counts:
                counts[k] += 1
        keys = {env: bool(os.environ.get(env)) for env in
                ("GBT_LLM_API_KEY", "ABLITERATION_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY")}
        try:
            import certifi
            ca = bool(certifi.where()) and os.path.isfile(certifi.where())
        except Exception:  # noqa: BLE001
            ca = False
        return {"kinds": len(kinds), "plugged": counts, "sockets": len(plugged),
                "keys": sum(1 for v in keys.values() if v), "ca": ca,
                "trusted": bool(P.is_trusted()),
                "full_open": (os.environ.get("GBT_OMNI_FULL_OPEN") == "1")}
    except Exception as e:  # noqa: BLE001
        return {"error": "%s: %s" % (type(e).__name__, str(e)[:80])}


def _system_state() -> dict:
    ps = _psutil()
    out = {}
    if ps is not None:
        try:
            out["cpu"] = round(ps.cpu_percent(interval=None), 2)
            vm = ps.virtual_memory()
            out["ram"] = round(vm.percent, 2)
            out["ram_used_mb"] = int(vm.used / 1024 / 1024)
            du = ps.disk_usage(str(ROOT.drive or "C:\\"))
            out["disk_free_gb"] = round(du.free / 1e9, 2)
            out["procs"] = len(ps.pids())
            out["boot_s"] = int(time.time() - ps.boot_time())
        except Exception as e:  # noqa: BLE001
            out["error"] = str(e)[:100]
    else:
        try:
            import shutil
            out["disk_free_gb"] = round(shutil.disk_usage(str(ROOT)).free / 1e9, 2)
            out["cpu"] = None
            out["ram"] = None
        except Exception:  # noqa: BLE001
            pass
    return out


def _files_state() -> dict:
    files = {
        "settings": STATE / "app-settings.json",
        "bindings": STATE / "asset_bindings.json",
        "ledger": STATE / "asset_bindings.jsonl",
        "moments": STATE / "moments.json",
        "console_data": ROOT / "state" / "console-data.js",
        "dh_rerig": STATE / "hd" / "rerig" / "dh-tentacle-rerig.glb",
    }
    return {k: _stat_file(p) for k, p in files.items()}


def _lines_state() -> dict:
    try:
        from . import omni_lines as _L
        r = _L.sample()
        ch = r.get("changed") or []
        return {"watched": r.get("watched"), "edges": r.get("edges"),
                "routes": r.get("routes"), "changed": len(ch),
                "last_path": (ch[-1]["path"] if ch else ""),
                "last_related": (ch[-1]["related_count"] if ch else 0),
                "at": r.get("at")}
    except Exception as e:  # noqa: BLE001
        return {"error": "%s: %s" % (type(e).__name__, str(e)[:80])}


def _proactive_state() -> dict:
    try:
        from . import proactive as P
        s = P.status()
        return {"running": s.get("running"), "counts": s.get("counts"),
                "tickets": len(s.get("tickets") or []), "last_error": s.get("last_error")}
    except Exception as e:  # noqa: BLE001
        return {"error": "%s: %s" % (type(e).__name__, str(e)[:80])}


def sample() -> dict:
    """读一遍所有域；与上次做逐字段 diff。"""
    now = time.time()
    snap = {
        "at": round(now, 3),
        "system": _system_state(),
        "omni": _omni_domains(),
        "memory": _memory_state(),
        "tentacle": {**_count_bindings(), **_tentacle_coverage()},
        "blueprint": _blueprint_state(),
        "files": _files_state(),
        "dh": _dh_state(),
        "lines": _lines_state(),
        "proactive": _proactive_state(),
    }
    with LOCK:
        prev = LAST.get("snap")
        LAST["snap"] = snap
        LAST["at"] = now
        changes = _diff(prev, snap, "") if prev else []
        HISTORY.append(snap)
        if len(HISTORY) > MAX_HISTORY:
            del HISTORY[: len(HISTORY) - MAX_HISTORY]
        if changes:
            rec = {"at": snap["at"], "changes": changes}
            EVENT_RING.append(rec)
            if len(EVENT_RING) > 500:
                del EVENT_RING[: len(EVENT_RING) - 500]
            try:
                EVENTS.parent.mkdir(parents=True, exist_ok=True)
                with EVENTS.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            except Exception:  # noqa: BLE001
                pass
        return {"snap": snap, "changes": changes,
                "history": len(HISTORY), "events": len(EVENT_RING)}


def _diff(a, b, prefix=""):
    out = []
    if a is None:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a.keys()) | set(b.keys())):
            if k == "at":
                continue
            path = (prefix + "." + k) if prefix else k
            if k not in a:
                out.append({"path": path, "from": None, "to": b[k], "kind": "added"})
            elif k not in b:
                out.append({"path": path, "from": a[k], "to": None, "kind": "removed"})
            else:
                out.extend(_diff(a[k], b[k], path))
        return out
    try:
        if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
            if abs(float(b) - float(a)) > 1e-9:
                return [{"path": prefix, "from": a, "to": b,
                         "delta": round(float(b) - float(a), 4), "kind": "changed"}]
            return []
        if str(a) != str(b):
            return [{"path": prefix, "from": a, "to": b, "kind": "changed"}]
    except Exception:  # noqa: BLE001
        pass
    return out


def monitor(force: bool = True) -> dict:
    if force or LAST.get("snap") is None:
        r = sample()
    else:
        with LOCK:
            r = {"snap": LAST.get("snap"), "changes": [], "history": len(HISTORY)}
    snap = r["snap"]
    recent = EVENT_RING[-12:]
    return {"ok": True, "sampled_at": snap["at"], "domains": snap,
            "changes": r["changes"], "recent": recent,
            "history": r.get("history", len(HISTORY)),
            "summary": {
                "domains": 8,
                "changes": len(r["changes"]),
                "recent_events": len(EVENT_RING),
            }}
