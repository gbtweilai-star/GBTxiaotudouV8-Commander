# -*- coding: utf-8 -*-
"""watchdog-run -- 看护一眼：本机内存 + 卡状态 + 训练进度 + OOM/报错扫描 + 推理进度。"""
from __future__ import annotations
import ctypes, json, os, re, ssl, urllib.request, urllib.parse
from pathlib import Path

import sys as _gbt_sys

for _gbt_s in (_gbt_sys.stdout, _gbt_sys.stderr):
    try:
        _gbt_s.reconfigure(encoding="utf-8")
    except Exception:
        pass


ROOT = Path(__file__).resolve().parents[2]
R = os.environ.get("WATCH_ROUND", "v44")


def avail_gb():
    try:
        class M(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        m = M()
        m.dwLength = ctypes.sizeof(M)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
        return round(m.ullAvailPhys / 1024 ** 3, 2)
    except Exception:
        return -1.0


def main():
    print("== 看护 · " + __import__("time").strftime("%H:%M:%S") + " ==")
    g = avail_gb()
    tag = "OK " if g >= 1.0 else ("AMBER" if g >= 0.5 else "RED ")
    print("W1 本机可用内存 %s %.2f GB（熔断阈 0.5 / 警戒 1.0）" % (tag, g))
    k = (os.environ.get("GBT_RUNPOD_API_KEY") or "").strip()
    if not k:
        p = ROOT / ".scratch" / ".runpod_key"
        k = p.read_text(encoding="utf-8").strip() if p.is_file() else ""
    pidf = ROOT / ".scratch" / ".pod_id"
    if not pidf.is_file():
        print("W2 无卡记录")
        return 0
    PID = pidf.read_text(encoding="ascii").strip()
    try:
        info = json.loads(urllib.request.urlopen(urllib.request.Request("https://rest.runpod.io/v1/pods/" + PID, headers={"Authorization": "Bearer " + k, "User-Agent": "M"}), timeout=30).read().decode())
        st = info.get("desiredStatus")
        print("W2 卡 %s 状态 %s" % (PID, st))
        pw = (info.get("env") or {}).get("JUPYTER_PASSWORD") or ""
    except Exception as e:
        print("W2 卡状态取不到:", str(e)[:60])
        return 0
    ctx = ssl.create_default_context()

    def gfile(n):
        try:
            return urllib.request.urlopen(urllib.request.Request("https://%s-8888.proxy.runpod.net/files/workspace/%s?token=%s" % (PID, n, urllib.parse.quote(pw)), headers={"User-Agent": "M"}), timeout=60, context=ctx).read().decode("utf-8", "replace")
        except Exception as e:
            return "ERR " + str(getattr(e, "code", type(e).__name__))
    tr = gfile("train_" + R + ".log")
    ch = gfile("chain_" + R + ".log")
    if tr.startswith("ERR"):
        print("W3 训练日志 " + tr)
    else:
        bars = [l.replace(chr(27), "") for l in tr.splitlines() if re.search(r"\d+/\d+ \[", l)]
        m = re.search(r"(\d+)/(\d+) \[([0-9:]+)<([0-9:]+)", bars[-1]) if bars else None
        oom = ("OutOfMemory" in tr) or ("CUDA out of memory" in tr)
        err = ("Traceback" in tr) or ("Error" in tr and "UserWarning" not in tr)
        print("W3 训练 %s" % (("%s/%s 已用 %s 剩余 %s" % m.groups()) if m else ("日志 %d 行（加载中）" % len(tr.splitlines()))))
        print("W4 OOM %s · 报错 %s · peak_vram 打印 %s" % ("RED" if oom else "OK", "RED" if err else "OK", "已有" if "peak_vram_gb" in tr else "尚无"))
    if not ch.startswith("ERR"):
        m2 = re.search(r"CHAIN_EXIT=(\d+)", ch)
        print("W5 链 " + ("已结束 exit=" + m2.group(1) if m2 else "运行中"))
    done = [n for n in ("accept", "comfy", "video", "forge", "offense", "spider", "sc") if not gfile(n + "_" + R + ".log").startswith("ERR")]
    print("W6 推理已出 %d/7 %s" % (len(done), done))
    _red = (g < 0.5) or ("CHAIN_EXIT=0" not in ch and "CHAIN_EXIT" in ch and "CHAIN_EXIT=0" not in ch)
    if not tr.startswith("ERR"):
        if ("OutOfMemory" in tr) or ("CUDA out of memory" in tr) or ("Traceback" in tr):
            _red = True
    _verdict = "RED（有事，先查）" if _red else ("AMBER（内存紧）" if g < 1.0 else "OK") 
    print("== 结论: " + _verdict + " ==")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
