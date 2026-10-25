# -*- coding: utf-8 -*-
"""进程读取安全层 —— 优先 psutil，坏了就自己读 /proc。

为什么需要它（实测根因，2026-10-25）：
    iSH 的 /proc/<pid>/stat **只有 39 个字段**（标准 Linux 是 52），
    缺 delayacct_blkio_ticks 等尾部字段。psutil 6.0.0 在
    `_pslinux.py:1799` 里硬取 `fields[39]` ⇒ IndexError ⇒
    `psutil.process_iter()` 直接炸，连带 task_manager / lobehub 两个能力位报 error。

口径（生产要求）：
    · **取不到就如实报"未读到"，绝不编数**
    · psutil 能用就用它（字段全、单位统一）
    · psutil 一崩就回落到 /proc 直读（字段少但 pid/name/cmdline/RSS/CPU ticks 都在）
    · 任何单进程读失败只跳过那一行，不连累整批
"""
from __future__ import annotations

import os
import time

PROC = "/proc"


# ── psutil 可用性探测（一次，缓存）─────────────────────────────
_PSUTIL_OK = None


def psutil_usable() -> bool:
    """真探一次：psutil 能不能读进程。iSH 上会因 /proc 字段不全而 False。"""
    global _PSUTIL_OK
    if _PSUTIL_OK is not None:
        return _PSUTIL_OK
    try:
        import psutil
        next(iter(psutil.process_iter(["pid"])))
        _PSUTIL_OK = True
    except Exception:
        _PSUTIL_OK = False
    return _PSUTIL_OK


# ── /proc 直读回落 ────────────────────────────────────────────
def _read(path: str, mode: str = "r") -> str:
    try:
        with open(path, mode) as f:
            return f.read()
    except Exception:
        return ""


def _proc_row(pid: str) -> dict | None:
    base = os.path.join(PROC, pid)
    # 🔴 iSH 的 /proc/<pid>/comm **是空的**（实测 0 字节），
    #    但 cmdline 能读（ps 命令就是这么列的）⇒ 名字从 cmdline 推导。
    name = _read(os.path.join(base, "comm")).strip()
    raw = _read(os.path.join(base, "cmdline"), "rb")
    if isinstance(raw, bytes):
        parts = [p.decode("utf-8", "replace") for p in raw.split(b"\x00") if p]
    else:
        parts = []
    if not name:
        if parts:
            name = os.path.basename(parts[0].split(" ")[0]) or parts[0][:28]
        else:
            name = "[pid %s]" % pid
    # RSS：/proc/<pid>/status 里的 VmRSS（kB）
    rss_kb = 0
    for ln in _read(os.path.join(base, "status")).splitlines():
        if ln.startswith("VmRSS:"):
            try:
                rss_kb = int(ln.split()[1])
            except (IndexError, ValueError):
                rss_kb = 0
            break
    # CPU ticks：/proc/<pid>/stat 的第 14、15 字段（utime, stime）
    # ⚠️ comm 里可能带空格/括号 ⇒ 从最后一个 ')' 之后开始数
    ticks = 0
    st = _read(os.path.join(base, "stat"))
    if st:
        try:
            tail = st[st.rfind(")") + 1:].split()
            ticks = int(tail[11]) + int(tail[12])          # utime=第14、stime=第15（整体计）
        except (IndexError, ValueError):
            ticks = 0
    # 🔴 iSH 的 /proc 只有最低限度：
    #    · comm   → 0 字节（名字只能从 cmdline 推）
    #    · status → 不存在（VmRSS 读不到）
    #    · stat 的 utime/stime → **恒为 0**（CPU 时间不记）
    #    所以取不到的列写 None，**绝不拿 0 冒充读数**。
    return {"pid": int(pid), "name": name[:28], "cmdline": parts,
            "rss_mb": round(rss_kb / 1024.0, 1) if rss_kb else None,
            "cpu_ticks": ticks, "_has_ticks": ticks > 0}


def _pids() -> list[str]:
    try:
        return [d for d in os.listdir(PROC) if d.isdigit()]
    except OSError:
        return []


def via_proc(sample_s: float = 0.5) -> list[dict]:
    """直接读 /proc。cpu 用两次采样算百分比（口径与 psutil 的 cpu_percent 接近）。"""
    first = {}
    for pid in _pids():
        r = _proc_row(pid)
        if r:
            first[pid] = r
    if not first:
        return []
    time.sleep(sample_s)
    hz = 100.0
    try:
        hz = float(os.sysconf("SC_CLK_TCK") or 100)
    except (ValueError, OSError):
        pass
    rows = []
    for pid, r in first.items():
        r2 = _proc_row(pid)
        if not r2:
            continue
        if r.get("_has_ticks"):
            d = max(r2["cpu_ticks"] - r["cpu_ticks"], 0)
            r2["cpu"] = round(d / hz / sample_s * 100.0, 1)
        else:
            r2["cpu"] = None                      # 未读到，不编 0
        r2.pop("cpu_ticks", None)
        r2.pop("_has_ticks", None)
        r2["src"] = "proc"
        rows.append(r2)
    return rows


# ── psutil 路径 ───────────────────────────────────────────────
def via_psutil() -> list[dict]:
    import psutil
    rows = []
    procs = list(psutil.process_iter(["pid", "name", "memory_info", "cpu_percent", "cmdline"]))
    for p in procs:                                  # 预热采样，否则 cpu_percent 恒 0
        try:
            p.cpu_percent(None)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    time.sleep(0.5)
    for p in procs:
        try:
            info = p.info
            mem = (info.get("memory_info").rss if info.get("memory_info") else 0) / 1048576.0
            try:
                cpu = float(p.cpu_percent(None) or 0.0)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                cpu = float(info.get("cpu_percent") or 0.0)
            rows.append({"pid": info["pid"], "name": (info.get("name") or "")[:28],
                         "cmdline": info.get("cmdline") or [],
                         "rss_mb": round(mem, 1), "cpu": round(cpu, 1), "src": "psutil"})
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        except Exception:
            continue                                  # 单条坏不连累整批
    return rows


def snapshot(fallback_sample: float = 0.5) -> dict:
    """统一入口：返回 {"ok":bool, "src":str, "rows":[...], "note":str}"""
    if psutil_usable():
        try:
            rows = via_psutil()
            return {"ok": True, "src": "psutil", "rows": rows,
                    "note": "psutil 全字段"}
        except Exception as e:                        # noqa: BLE001
            note = "%s: %s" % (type(e).__name__, str(e)[:80])
    else:
        note = "psutil 在本机读不到进程（/proc/<pid>/stat 字段不全），已回落到 /proc 直读"
    rows = via_proc(fallback_sample)
    unread = []
    if rows and rows[0].get("cpu") is None:
        unread.append("CPU")
    if rows and rows[0].get("rss_mb") is None:
        unread.append("内存")
    if unread:
        note += "｜本机 /proc 不提供 %s ⇒ 该列写『未读到』，不编 0" % "/".join(unread)
    return {"ok": bool(rows), "src": "proc", "rows": rows, "note": note}


if __name__ == "__main__":
    d = snapshot()
    print("  来源:", d["src"], "· 进程数:", len(d["rows"]))
    print("  说明:", d["note"])
    def _fmt(v, unit):
        return "未读到" if v is None else ("%.1f %s" % (v, unit))
    for r in sorted(d["rows"], key=lambda x: -(x.get("cpu") or 0))[:8]:
        print("    %-7d %-20s rss=%-10s cpu=%s" %
              (r["pid"], r["name"], _fmt(r.get("rss_mb"), "MB"), _fmt(r.get("cpu"), "%")))
