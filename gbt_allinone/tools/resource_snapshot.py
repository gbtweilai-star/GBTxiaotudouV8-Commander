# -*- coding: utf-8 -*-
# gbt-capability: resource_snapshot  ⛔ 开发者：自由的风 · GBT小土豆V8 · 永久钢印
"""本机资源快照（resource_snapshot）—— 只读、零第三方依赖。

对照上游参考项目的「本机资源快照」：只蒸**读数口径**，不搬它的监控面板栈。
Windows 用 ctypes 读 GlobalMemoryStatusEx / GetSystemTimes / GetTickCount64，
磁盘用 shutil.disk_usage；`psutil` 可选（没有就不报进程数，不硬装）。
不写盘、不起进程、不出网；采样只 sleep 0.15s 取 CPU 两帧差。
"""
from __future__ import annotations

import ctypes
import hashlib
import os
import platform
import shutil
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
FIELDS = ("cpu_percent", "mem_total_mb", "mem_used_mb", "mem_percent",
          "disk_total_gb", "disk_used_gb", "disk_percent", "uptime_s")


class SnapshotError(ValueError):
    pass


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong), ("dwHighDateTime", ctypes.c_ulong)]


def _ft(v: _FILETIME) -> int:
    return (int(v.dwHighDateTime) << 32) | int(v.dwLowDateTime)


def _mem() -> dict:
    if os.name != "nt":
        return {}
    try:
        st = _MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(st)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return {}
        total = int(st.ullTotalPhys)
        avail = int(st.ullAvailPhys)
        used = max(0, total - avail)
        return {"mem_total_mb": round(total / 1048576, 1),
                "mem_used_mb": round(used / 1048576, 1),
                "mem_percent": round(used * 100.0 / total, 1) if total else 0.0}
    except Exception:  # noqa: BLE001
        return {}


def _cpu() -> dict:
    if os.name != "nt":
        return {}
    try:
        k32 = ctypes.windll.kernel32
        idle, kernel, user = _FILETIME(), _FILETIME(), _FILETIME()
        if not k32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return {}
        a = (_ft(idle), _ft(kernel), _ft(user))
        time.sleep(0.15)
        if not k32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return {}
        b = (_ft(idle), _ft(kernel), _ft(user))
        di, dk, du = (b[i] - a[i] for i in range(3))
        total = dk + du
        if total <= 0:
            return {"cpu_percent": 0.0}
        busy = max(0, total - di)
        return {"cpu_percent": round(min(100.0, busy * 100.0 / total), 1)}
    except Exception:  # noqa: BLE001
        return {}


def _uptime() -> float:
    if os.name != "nt":
        return 0.0
    try:
        return round(ctypes.windll.kernel32.GetTickCount64() / 1000.0, 1)
    except Exception:  # noqa: BLE001
        return 0.0


def _disk() -> dict:
    try:
        u = shutil.disk_usage(str(_ROOT))
        total = int(u.total)
        used = int(u.used)
        return {"disk_total_gb": round(total / 1e9, 2),
                "disk_used_gb": round(used / 1e9, 2),
                "disk_percent": round(used * 100.0 / total, 1) if total else 0.0}
    except Exception:  # noqa: BLE001
        return {}


def _proc_count():
    try:
        import psutil  # type: ignore
        return int(len(psutil.pids()))
    except Exception:  # noqa: BLE001
        return None


def collect() -> dict:
    raw = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "host": platform.node() or "?",
           "platform": platform.system() + " " + platform.release(),
           "uptime_s": _uptime(), "process_count": _proc_count()}
    raw.update(_mem())
    raw.update(_cpu())
    raw.update(_disk())
    return raw


def normalize(raw) -> dict:
    if not isinstance(raw, dict):
        raise SnapshotError("snapshot 必须是对象")
    out = {"at": str(raw.get("at") or "").strip(), "host": str(raw.get("host") or "?")[:80],
           "platform": str(raw.get("platform") or "?")[:80],
           "uptime_s": float(raw.get("uptime_s") or 0.0),
           "process_count": raw.get("process_count")}
    for k in FIELDS:
        try:
            v = float(raw.get(k, 0.0))
        except (TypeError, ValueError):
            raise SnapshotError("%s 必须是数字" % k)
        if k.endswith("_percent") and not (0.0 <= v <= 100.0):
            raise SnapshotError("%s 范围 0..100" % k)
        if v < 0:
            raise SnapshotError("%s 不能为负" % k)
        out[k] = round(v, 2)
    if out["uptime_s"] < 0:
        raise SnapshotError("uptime_s 不能为负")
    if out["process_count"] is not None:
        try:
            out["process_count"] = int(out["process_count"])
        except (TypeError, ValueError):
            raise SnapshotError("process_count 必须是整数或 null")
    return out


def snapshot() -> dict:
    raw = collect()
    try:
        return {"ok": True, **normalize(raw)}
    except SnapshotError as e:
        return {"ok": False, "error": "user_error: %s" % e, "raw_keys": sorted(raw)}


def verify() -> dict:
    checks = []

    def ck(name, cond, got=None):
        checks.append({"name": name, "ok": bool(cond), "got": got})

    fixture = {"at": "2026-11-03T00:00:00", "host": "test", "platform": "Windows",
               "cpu_percent": 12.5, "mem_total_mb": 16000, "mem_used_mb": 8000,
               "mem_percent": 50.0, "disk_total_gb": 500, "disk_used_gb": 250,
               "disk_percent": 50.0, "uptime_s": 3600, "process_count": 200}
    n = normalize(fixture)
    ck("归一", n["cpu_percent"] == 12.5 and n["process_count"] == 200)
    ck("百分号范围", _raises(lambda: normalize(dict(fixture, cpu_percent=101))))
    ck("负数拒", _raises(lambda: normalize(dict(fixture, mem_used_mb=-1))))
    ck("非数字拒", _raises(lambda: normalize(dict(fixture, disk_total_gb="x"))))
    ck("非对象拒", _raises(lambda: normalize("x")))
    ck("process_count null 允许", normalize(dict(fixture, process_count=None))["process_count"] is None)
    s = snapshot()
    ck("真采样 ok", s.get("ok") is True, s.get("error"))
    ck("有 cpu", isinstance(s.get("cpu_percent"), (int, float)))
    ck("有 mem", s.get("mem_total_mb", 0) > 0)
    ck("有 disk", s.get("disk_total_gb", 0) > 0)
    ck("uptime 非负", s.get("uptime_s", -1) >= 0)
    ck("host 非空", bool(s.get("host")))
    ck("平台串", bool(s.get("platform")))
    ck("schema 可达", "fields" in run("schema") and "note" in run("schema"))
    ck("snapshot op", run("snapshot")["ok"] is True)
    ck("未知 op 拒", _raises(lambda: run("teleport")))
    return {"ok": all(c["ok"] for c in checks), "checks": len(checks),
            "failed": [c for c in checks if not c["ok"]],
            "sha": hashlib.sha256(str(checks).encode()).hexdigest()[:12]}


def _raises(fn) -> bool:
    try:
        fn()
        return False
    except (SnapshotError, ValueError):
        return True


def run(op="snapshot", **params):
    op = str(op or "snapshot").lower()
    if op == "schema":
        return {"ok": True, "fields": list(FIELDS), "optional": ["process_count"],
                "units": {"cpu_percent": "%", "mem_*_mb": "MB", "disk_*_gb": "GB",
                          "uptime_s": "秒"},
                "note": "只读采样；ctypes + shutil；不引第三方（psutil 可选）"}
    if op == "snapshot":
        return snapshot()
    if op == "normalize":
        try:
            return {"ok": True, "snapshot": normalize(params.get("snapshot"))}
        except SnapshotError as e:
            return {"ok": False, "error": "user_error: %s" % e}
    if op == "verify":
        return verify()
    raise ValueError("未知 op: %s（schema/snapshot/normalize/verify）" % op)
